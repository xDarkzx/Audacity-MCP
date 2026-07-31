import json
import os
import re
from mcp.server.fastmcp import FastMCP
from audacity_mcp_shared.error_codes import AudacityMCPError, ErrorCode
from audacity_mcp_shared.constants import (
    ALLOWED_EXPORT_FORMATS,
    CHAPTER_FORMATS,
    MAX_LABEL_LENGTH,
)

# A point label has zero width, so there is no region to select for deletion.
# SplitDelete needs a non-empty span, hence a hair either side.
POINT_LABEL_EPSILON = 0.001

MAX_BATCH_LABELS = 500
MAX_EXPORT_SEGMENTS = 100

# How far a leftover label's start may drift and still be recognised as the
# one whose audio was just deleted, rather than a different label.
_LEFTOVER_START_TOLERANCE = 0.01


def find_leftover_label(labels: list[dict], target: dict) -> int | None:
    """Index of the marker left behind where target's audio was, or None if gone.

    Deleting a label's audio does not delete the label - it collapses to a
    zero-length marker at the start of the cut. Finding it by text plus that
    position works even when the delete shifted other labels around; looking it
    up by its original index only works if nothing moved, which is exactly the
    case that needs handling.
    """
    for label in labels:
        if (label["text"] == target["text"]
                and abs(label["start"] - target["start"]) <= _LEFTOVER_START_TOLERANCE):
            return label["index"]
    return None


def _is_label_leaf(node) -> bool:
    """True if node is a [start, end, text] triple as GetInfo reports labels."""
    return (isinstance(node, list) and len(node) == 3
            and isinstance(node[0], (int, float))
            and isinstance(node[1], (int, float)) and isinstance(node[2], str))


async def get_parsed_labels(client) -> list[dict]:
    """Every label in the project, flattened into SetLabel's index order.

    Returns [{"index", "start", "end", "text", "track"}, ...] where "index" is
    the flat, project-wide position SetLabel's Label= parameter expects and
    "track" is the ordinal of the enclosing label track (None when Audacity
    reports a flat list with no track grouping).

    GetInfo Type=Labels returns JSON whose structure varies by Audacity version
    (nested per label-track vs. flattened), so this walks the parsed JSON
    looking for [start, end, text]-shaped leaves rather than assuming one
    fixed schema. Malformed or empty output yields an empty list rather than
    raising - callers treat "no labels" and "unreadable labels" the same way.
    """
    result = await client.execute("GetInfo", Type="Labels")
    raw = result.get("message", "")
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return []
    if not isinstance(parsed, list):
        return []

    labels: list[dict] = []

    def _walk(node, track):
        if not isinstance(node, list):
            return
        if _is_label_leaf(node):
            labels.append({
                "index": len(labels),
                "start": float(node[0]),
                "end": float(node[1]),
                "text": node[2],
                "track": track,
            })
            return
        for item in node:
            _walk(item, track)

    for ordinal, group in enumerate(parsed):
        _walk(group, None if _is_label_leaf(group) else ordinal)

    return labels


async def count_existing_labels(client) -> int:
    """Total label count across all label tracks in the project.

    SetLabel's Label= parameter is a flat index of the label to edit - it is
    NOT "whichever label was just added". AddLabel doesn't report the new
    label's index back, so the only way to target it correctly is to know
    how many labels existed right before adding it (the new one lands at
    that index, since AddLabel appends). Getting this wrong was a real bug:
    every SetLabel(Label=0, ...) call retargeted the very first label ever
    created instead of the one just added, leaving every other label blank.
    """
    return len(await get_parsed_labels(client))


async def get_label_track_indices(client) -> list[int]:
    """Absolute track indices of the label tracks, as SelectTracks Track= expects.

    Label indices from get_parsed_labels are relative to the label tracks only,
    but SelectTracks counts every track in the project, so the two have to be
    mapped through this before a label's track can be selected.
    """
    result = await client.execute("GetInfo", Type="Tracks")
    raw = result.get("message", "")
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [i for i, track in enumerate(parsed)
            if isinstance(track, dict) and track.get("kind") == "label"]


def _validate_label_text(text: str) -> None:
    if len(text) > MAX_LABEL_LENGTH:
        raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, f"Label text too long (max {MAX_LABEL_LENGTH})")


async def add_labels_at(client, labels: list[dict]) -> int:
    """Add labels at explicit time ranges. Returns the index of the first one added.

    Each item is {"start": float, "end": float, "text": str}. AddLabel appends
    and reports nothing back, so the i-th label added lands at base + i where
    base is the label count before the batch started - see count_existing_labels.
    """
    base = await count_existing_labels(client)
    for offset, label in enumerate(labels):
        await client.execute("SelectTime", Start=label["start"], End=label["end"])
        await client.execute("AddLabel")
        text = label.get("text", "")
        if text:
            await client.execute("SetLabel", Label=base + offset, Text=text)
    return base


def _command_report(result: dict) -> dict:
    """Audacity's own reply to one command, for surfacing in a failure payload."""
    return {
        "success": result.get("success", False),
        "message": result.get("message", ""),
        "raw": result.get("raw", ""),
    }


async def remove_label(client, index: int) -> dict:
    """Remove one label by flat index, leaving all audio untouched.

    Audacity has no scripting command for deleting a single label, so this
    selects the label's own span on its own label track and split-deletes it.
    Audio tracks are never in the selection, so nothing downstream shifts.
    Shared by label_delete and by label_delete_region's cleanup step.
    """
    if index < 0:
        raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "index must be >= 0")

    labels = await get_parsed_labels(client)
    if index >= len(labels):
        raise AudacityMCPError(
            ErrorCode.VALUE_OUT_OF_RANGE,
            f"No label at index {index} — project has {len(labels)} label(s)")

    target = labels[index]
    label_tracks = await get_label_track_indices(client)
    if target["track"] is None or target["track"] >= len(label_tracks):
        raise AudacityMCPError(
            ErrorCode.COMMAND_FAILED,
            "Could not work out which track this label belongs to. "
            "Delete it directly in Audacity, or use label_export/label_import "
            "to rewrite the label track.")
    absolute_track = label_tracks[target["track"]]

    if target["end"] > target["start"]:
        region_start, region_end = target["start"], target["end"]
    else:
        region_start = max(0.0, target["start"] - POINT_LABEL_EPSILON)
        region_end = target["start"] + POINT_LABEL_EPSILON

    collateral = [label for label in labels
                  if label["track"] == target["track"]
                  and label["index"] != index
                  and region_start <= label["start"] and label["end"] <= region_end]

    select_tracks = await client.execute(
        "SelectTracks", Track=absolute_track, TrackCount=1, Mode="Set")
    select_time = await client.execute("SelectTime", Start=region_start, End=region_end)
    split_delete = await client.execute("SplitDelete")

    remaining = await get_parsed_labels(client)
    if len(remaining) >= len(labels):
        # Report what Audacity actually said rather than guessing at a cause -
        # the count not dropping is an observation, not a diagnosis.
        return {
            "success": False,
            "message": (f"The label count did not drop after SplitDelete "
                        f"({len(labels)} before, {len(remaining)} after). Audacity's own "
                        f"reply to each command is under 'audacity_responses'."),
            "index": index,
            "count_before": len(labels),
            "count_after": len(remaining),
            "target_was_point_label": target["end"] <= target["start"],
            "selected_region": {"start": region_start, "end": region_end},
            "selected_track": absolute_track,
            "audacity_responses": {
                "SelectTracks": _command_report(select_tracks),
                "SelectTime": _command_report(select_time),
                "SplitDelete": _command_report(split_delete),
            },
        }

    restored = 0
    if collateral:
        await add_labels_at(client, [
            {"start": label["start"], "end": label["end"], "text": label["text"]}
            for label in collateral
        ])
        restored = len(collateral)

    return {
        "success": True,
        "index": index,
        "deleted": {"start": target["start"], "end": target["end"], "text": target["text"]},
        "restored": restored,
        "count_before": len(labels),
        "count_after": len(remaining) + restored,
    }


def format_chapter_timestamp(seconds: float) -> str:
    """Seconds to HH:MM:SS.mmm, the timestamp shape every chapter format here uses."""
    total_ms = int(round(max(0.0, seconds) * 1000))
    hours, remainder = divmod(total_ms, 3600000)
    minutes, remainder = divmod(remainder, 60000)
    secs, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"


_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9 _.-]")


def sanitize_filename(text: str, fallback: str = "segment") -> str:
    """Label text to a filename component that is safe on Windows and POSIX alike."""
    cleaned = _UNSAFE_FILENAME_CHARS.sub("", text)
    cleaned = re.sub(r"\s+", "_", cleaned).strip("._")[:60].strip("._")
    return cleaned or fallback


def _chapter_title(label: dict, position: int) -> str:
    return label["text"].strip() or f"Chapter {position}"


def format_chapters_simple(labels: list[dict]) -> str:
    """Simple chapter format: one "HH:MM:SS.mmm Title" line per chapter."""
    lines = [f"{format_chapter_timestamp(label['start'])} {_chapter_title(label, i + 1)}"
             for i, label in enumerate(labels)]
    return "\n".join(lines) + "\n"


def format_chapters_cue(labels: list[dict]) -> str:
    """Minimal cue sheet. INDEX times are MM:SS:FF with 75 frames per second."""
    lines = ['FILE "audio" WAVE']
    for i, label in enumerate(labels):
        title = _chapter_title(label, i + 1).replace('"', "'")
        total_frames = int(round(label["start"] * 75))
        minutes, remainder = divmod(total_frames, 75 * 60)
        secs, frames = divmod(remainder, 75)
        lines.append(f"  TRACK {i + 1:02d} AUDIO")
        lines.append(f'    TITLE "{title}"')
        lines.append(f"    INDEX 01 {minutes:02d}:{secs:02d}:{frames:02d}")
    return "\n".join(lines) + "\n"


def format_chapters_podlove(labels: list[dict]) -> str:
    """Podlove Simple Chapters JSON, as consumed by most podcast hosts."""
    chapters = [{"startTime": format_chapter_timestamp(label["start"]),
                 "title": _chapter_title(label, i + 1)}
                for i, label in enumerate(labels)]
    return json.dumps({"version": "1.2.0", "chapters": chapters}, indent=2) + "\n"


_CHAPTER_FORMATTERS = {
    "simple": format_chapters_simple,
    "cue": format_chapters_cue,
    "podlove": format_chapters_podlove,
}


def register(mcp: FastMCP):
    from audacity_mcp.main import client

    @mcp.tool()
    async def label_add(text: str = "") -> dict:
        """Add a label at the current cursor position or selection.

        Args:
            text: Label text. Default: empty
        """
        _validate_label_text(text)
        index = await count_existing_labels(client) if text else 0
        result = await client.execute("AddLabel")
        if text:
            await client.execute("SetLabel", Label=index, Text=text)
        return result

    @mcp.tool()
    async def label_add_at(start: float, end: float, text: str = "") -> dict:
        """Add a label at a specific time range.

        Args:
            start: Start time in seconds
            end: End time in seconds
            text: Label text. Default: empty
        """
        if start < 0:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "Start must be >= 0")
        if end < start:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "End must be >= start")
        _validate_label_text(text)
        index = await count_existing_labels(client) if text else 0
        await client.execute("SelectTime", Start=start, End=end)
        result = await client.execute("AddLabel")
        if text:
            await client.execute("SetLabel", Label=index, Text=text)
        return result

    @mcp.tool()
    async def label_get_all() -> dict:
        """Get all labels in the project as Audacity's raw GetInfo response.

        Prefer label_list — it returns the same labels already parsed, with the
        index each one needs for label_edit and label_delete.
        """
        return await client.execute("GetInfo", Type="Labels")

    @mcp.tool()
    async def label_list() -> dict:
        """List every label with its index, timing and text.

        Returns labels sorted by Audacity's own flat index, which is what
        label_edit and label_delete take. Call this first whenever you need to
        modify a specific label, rather than guessing an index.
        """
        labels = await get_parsed_labels(client)
        return {"success": True, "count": len(labels), "labels": labels}

    @mcp.tool()
    async def label_find(query: str) -> dict:
        """Find labels whose text contains a search string (case-insensitive).

        Useful for locating a specific marker in a long recording without
        reading through every label.

        Args:
            query: Text to search for within label text
        """
        if not query.strip():
            raise AudacityMCPError(ErrorCode.INVALID_PARAMETER, "query must not be empty")
        needle = query.lower()
        matches = [label for label in await get_parsed_labels(client)
                   if needle in label["text"].lower()]
        return {"success": True, "query": query, "count": len(matches), "matches": matches}

    @mcp.tool()
    async def label_edit(
        index: int,
        text: str | None = None,
        start: float | None = None,
        end: float | None = None,
    ) -> dict:
        """Edit an existing label's text and/or timing. Only the fields you pass are changed.

        Get the index from label_list. Renaming a label is label_edit(index,
        text="..."); moving one of its boundaries is label_edit(index, start=...).

        Args:
            index: Flat label index from label_list
            text: New label text. Default: unchanged
            start: New start time in seconds. Default: unchanged
            end: New end time in seconds. Default: unchanged
        """
        if index < 0:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "index must be >= 0")
        if text is None and start is None and end is None:
            raise AudacityMCPError(ErrorCode.MISSING_PARAMETER,
                                   "Provide at least one of text, start, end")
        if text is not None:
            _validate_label_text(text)
        if start is not None and start < 0:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "start must be >= 0")

        labels = await get_parsed_labels(client)
        if index >= len(labels):
            raise AudacityMCPError(
                ErrorCode.VALUE_OUT_OF_RANGE,
                f"No label at index {index} — project has {len(labels)} label(s)")

        before = labels[index]
        new_start = before["start"] if start is None else start
        new_end = before["end"] if end is None else end
        if new_end < new_start:
            raise AudacityMCPError(
                ErrorCode.VALUE_OUT_OF_RANGE,
                f"end ({new_end}) must be >= start ({new_start})")

        params: dict = {"Label": index}
        if text is not None:
            params["Text"] = text
        if start is not None:
            params["Start"] = start
        if end is not None:
            params["End"] = end
        result = await client.execute("SetLabel", **params)

        return {
            "success": result.get("success", False),
            "index": index,
            "before": {"start": before["start"], "end": before["end"], "text": before["text"]},
            "after": {
                "start": new_start,
                "end": new_end,
                "text": before["text"] if text is None else text,
            },
        }

    @mcp.tool()
    async def label_add_batch(labels: list[dict]) -> dict:
        """Add many labels at once — a whole marker list in one call.

        Each item is {"start": seconds, "end": seconds (optional, defaults to
        start for a point label), "text": string (optional)}. Every item is
        validated before anything is sent to Audacity, so a bad item fails the
        whole call rather than leaving a half-written list behind.

        Args:
            labels: List of {"start", "end", "text"} label definitions
        """
        if not labels:
            raise AudacityMCPError(ErrorCode.INVALID_PARAMETER, "labels must not be empty")
        if len(labels) > MAX_BATCH_LABELS:
            raise AudacityMCPError(
                ErrorCode.VALUE_OUT_OF_RANGE,
                f"Too many labels ({len(labels)}), max {MAX_BATCH_LABELS} per call")

        normalized = []
        for position, item in enumerate(labels):
            if not isinstance(item, dict):
                raise AudacityMCPError(ErrorCode.INVALID_PARAMETER,
                                       f"Label {position} must be an object with a start time")
            if item.get("start") is None:
                raise AudacityMCPError(ErrorCode.MISSING_PARAMETER,
                                       f"Label {position} is missing 'start'")
            try:
                start = float(item["start"])
                end = float(item["end"]) if item.get("end") is not None else start
            except (TypeError, ValueError):
                raise AudacityMCPError(ErrorCode.INVALID_PARAMETER,
                                       f"Label {position} has a non-numeric start or end")
            if start < 0:
                raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE,
                                       f"Label {position}: start must be >= 0")
            if end < start:
                raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE,
                                       f"Label {position}: end must be >= start")
            text = item.get("text") or ""
            _validate_label_text(text)
            normalized.append({"start": start, "end": end, "text": text})

        base_index = await add_labels_at(client, normalized)
        return {"success": True, "added": len(normalized), "base_index": base_index}

    @mcp.tool()
    async def label_import(path: str) -> dict:
        """Import labels from a text file.

        Args:
            path: Absolute path to the labels text file
        """
        if not os.path.isabs(path):
            raise AudacityMCPError(ErrorCode.INVALID_PATH, "Path must be absolute")
        return await client.execute("ImportLabels", Filename=path)

    @mcp.tool()
    async def label_export(path: str) -> dict:
        """Export all labels to a text file.

        Args:
            path: Absolute path for the output labels file
        """
        if not os.path.isabs(path):
            raise AudacityMCPError(ErrorCode.INVALID_PATH, "Path must be absolute")
        return await client.execute("ExportLabels", Filename=path)

    @mcp.tool()
    async def label_regular_intervals(
        interval: float = 30.0,
        adjust: bool = False,
        label_text: str = "",
    ) -> dict:
        """Create labels at regular time intervals across the selection or project.

        Args:
            interval: Time between labels in seconds. Default: 30
            adjust: Adjust interval to fit selection evenly. Default: False
            label_text: Text for each label (labels will be numbered). Default: empty
        """
        if interval <= 0:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "interval must be > 0")
        _validate_label_text(label_text)
        params = {"Interval": interval, "Adjust": adjust}
        if label_text:
            params["Label"] = label_text
        return await client.execute("RegularIntervalLabels", **params)

    @mcp.tool()
    async def label_delete(index: int) -> dict:
        """Delete a single label without touching the audio.

        Get the index from label_list. Audacity has no scripting command for
        deleting one label, so this selects the label's own span on its own
        label track and split-deletes it — audio tracks are never in the
        selection, and nothing downstream shifts in time.

        Other labels on the same track that sit entirely inside the deleted
        label's span would be removed as collateral, so they are re-added
        afterwards. A label that only partially overlaps the span may be
        trimmed to the boundary; check label_list afterwards if labels on that
        track overlap each other.

        To delete a label *and* the audio under it, use label_delete_region.

        Args:
            index: Flat label index from label_list
        """
        return await remove_label(client, index)

    @mcp.tool()
    async def label_delete_region(
        index: int,
        close_gap: bool = True,
        delete_label: bool = True,
    ) -> dict:
        """Delete the audio under ONE label — label_delete_regions for a single label.

        By default the gap closes and everything after shifts left, exactly as
        label_delete_regions does. Pass close_gap=False to leave silence of the
        same length instead, keeping the timeline length and everything after it
        in place.

        All tracks are selected first, so label tracks ripple along with the
        audio and later labels stay aligned with it.

        Deleting the audio does NOT remove the label — it collapses to a
        zero-length marker sitting where the audio used to be. This tool clears
        that leftover marker too, matching what clicking a label and pressing
        Delete does in Audacity: the audio and the label both go. Pass
        delete_label=False to keep it as a marker of where the cut was made.
        Use label_delete instead to remove a label without touching any audio.

        Args:
            index: Flat label index from label_list
            close_gap: Close the gap and shift later audio left. Default: True
            delete_label: Also remove the label left behind. Default: True
        """
        if index < 0:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "index must be >= 0")

        labels = await get_parsed_labels(client)
        if index >= len(labels):
            raise AudacityMCPError(
                ErrorCode.VALUE_OUT_OF_RANGE,
                f"No label at index {index} — project has {len(labels)} label(s)")

        target = labels[index]
        if target["end"] <= target["start"]:
            raise AudacityMCPError(
                ErrorCode.VALIDATION_FAILED,
                f"Label {index} is a point label with no audio under it. Give it a "
                "start and end time first, or use label_delete to remove the marker.")

        await client.execute("SelAllTracks")
        await client.execute("SelectTime", Start=target["start"], End=target["end"])
        result = await client.execute_long("Delete" if close_gap else "SplitDelete")

        label_removed = False
        label_note = None
        if delete_label:
            leftover_index = find_leftover_label(await get_parsed_labels(client), target)
            if leftover_index is None:
                # Nothing left to clear - this Audacity dropped the label along
                # with its audio, which is the end state we were after anyway.
                label_removed = True
            else:
                removal = await remove_label(client, leftover_index)
                label_removed = bool(removal.get("success"))
                if not label_removed:
                    label_note = removal.get("message")

        remaining = await get_parsed_labels(client)
        return {
            "success": result.get("success", False),
            "index": index,
            "deleted": {"start": target["start"], "end": target["end"], "text": target["text"]},
            "closed_gap": close_gap,
            "label_removed": label_removed,
            "duration_removed": round(target["end"] - target["start"], 6),
            "count_before": len(labels),
            "count_after": len(remaining),
            **({"label_note": label_note} if label_note else {}),
        }

    @mcp.tool()
    async def label_cut_regions() -> dict:
        """Cut the audio under every label to the clipboard, closing the gaps.

        Acts on labeled regions within the current selection on the SELECTED
        AUDIO TRACKS — select the audio tracks and time range first. Because the
        timeline closes up, the labeled regions collapse rather than surviving
        unchanged — re-read label_list afterwards to see what remains.
        """
        return await client.execute_long("CutLabels")

    @mcp.tool()
    async def label_delete_regions() -> dict:
        """Delete the audio under every label, closing the gaps.

        Label every unwanted stretch — bad takes, dead air, noise bursts — then
        remove them all in one pass. Use label_delete_region for a single label.
        Acts on labeled regions within the current selection on the SELECTED
        AUDIO TRACKS — select the audio tracks and time range first. Because the
        timeline closes up, the labeled regions collapse rather than surviving
        unchanged — re-read label_list afterwards to see what remains.
        """
        return await client.execute_long("DeleteLabels")

    @mcp.tool()
    async def label_silence_regions() -> dict:
        """Replace the audio under every label with silence, keeping the timeline length.

        Use when the material must not get shorter — redacting a name, muting a
        noise burst in a take that has to stay in sync. Acts on labeled regions
        within the current selection on the SELECTED AUDIO TRACKS — select the
        audio tracks and time range first. The labels themselves stay where they are.
        """
        return await client.execute_long("SilenceLabels")

    @mcp.tool()
    async def label_split_regions() -> dict:
        """Split the audio clips at every label boundary.

        Prepares segment boundaries for separate handling without removing
        anything. Acts on labeled regions within the current selection
        on the SELECTED AUDIO TRACKS — select the audio tracks and time range
        first. The labels themselves stay where they are.
        """
        return await client.execute_long("SplitLabels")

    @mcp.tool()
    async def label_join_regions() -> dict:
        """Join the audio clips across every labeled region back together.

        The inverse of label_split_regions. Acts on labeled regions within the
        current selection on the SELECTED AUDIO TRACKS — select the audio tracks
        and time range first. The labels themselves stay where they are.
        """
        return await client.execute_long("JoinLabels")

    @mcp.tool()
    async def label_export_chapters(path: str, format: str = "simple") -> dict:
        """Export labels as a chapter/marker file.

        Turns a label track into a standard marker file — chapter navigation for
        long-form audio, a track listing for a continuous mix, an index for a
        lecture or interview recording. Formats: "simple" (HH:MM:SS.mmm Title
        per line), "cue" (cue sheet), "podlove" (Podlove Simple Chapters JSON).
        Labels with no text become "Chapter 1", "Chapter 2" and so on.

        Args:
            path: Absolute path for the output file (must not already exist)
            format: Chapter format — simple, cue or podlove. Default: simple
        """
        from audacity_mcp.tools.project_tools import _safe_path

        if format not in CHAPTER_FORMATS:
            raise AudacityMCPError(
                ErrorCode.INVALID_FORMAT,
                f"format must be one of {sorted(CHAPTER_FORMATS)}")
        path = _safe_path(path)
        if os.path.exists(path):
            raise AudacityMCPError(
                ErrorCode.INVALID_PATH,
                f"File already exists: {path}. Use a different filename to avoid overwriting.")

        labels = await get_parsed_labels(client)
        if not labels:
            raise AudacityMCPError(ErrorCode.VALIDATION_FAILED,
                                   "No labels in the project to export")
        labels = sorted(labels, key=lambda label: label["start"])

        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(_CHAPTER_FORMATTERS[format](labels))

        return {"success": True, "path": path, "format": format, "chapters": len(labels)}

    @mcp.tool()
    async def label_export_audio_segments(
        directory: str,
        format: str = "wav",
        num_channels: int = 2,
    ) -> dict:
        """Export the audio under each label as its own file.

        Splits a long recording into per-segment audio files, named
        "01_Segment_Title.wav" and so on from the label text. ALWAYS tell the
        user which directory the files will be written to BEFORE calling this.
        Point labels (zero length) have no audio to export and are skipped.
        Existing files are never overwritten — they are skipped and reported.
        This can take a while for many or long segments.

        Args:
            directory: Absolute path to the output directory
            format: Audio format — wav, mp3, ogg, flac, aiff, mp4. Default: wav
            num_channels: 1 for mono, 2 for stereo. Default: 2
        """
        from audacity_mcp.tools.project_tools import _safe_path

        if format not in ALLOWED_EXPORT_FORMATS:
            raise AudacityMCPError(
                ErrorCode.INVALID_FORMAT,
                f"format must be one of {sorted(ALLOWED_EXPORT_FORMATS)}")
        if num_channels not in (1, 2):
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE,
                                   "num_channels must be 1 (mono) or 2 (stereo)")
        directory = _safe_path(directory)

        labels = await get_parsed_labels(client)
        if not labels:
            raise AudacityMCPError(ErrorCode.VALIDATION_FAILED,
                                   "No labels in the project to export")
        regions = [label for label in labels if label["end"] > label["start"]]
        skipped_point_labels = len(labels) - len(regions)
        if not regions:
            raise AudacityMCPError(
                ErrorCode.VALIDATION_FAILED,
                "Every label is a point label with no audio region to export. "
                "Give the labels a start and end time first.")
        if len(regions) > MAX_EXPORT_SEGMENTS:
            raise AudacityMCPError(
                ErrorCode.VALUE_OUT_OF_RANGE,
                f"Too many segments ({len(regions)}), max {MAX_EXPORT_SEGMENTS} per call")

        os.makedirs(directory, exist_ok=True)
        await client.execute("SelAllTracks")

        exported = []
        skipped_existing = []
        for position, label in enumerate(regions, start=1):
            filename = f"{position:02d}_{sanitize_filename(label['text'])}.{format}"
            full_path = os.path.join(directory, filename)
            if os.path.exists(full_path):
                skipped_existing.append(full_path)
                continue
            await client.execute("SelectTime", Start=label["start"], End=label["end"])
            await client.execute_long("Export2", Filename=full_path, NumChannels=num_channels)
            exported.append({
                "index": label["index"],
                "path": full_path,
                "created": os.path.exists(full_path) and os.path.getsize(full_path) > 0,
            })

        return {
            "success": bool(exported) and all(item["created"] for item in exported),
            "directory": directory,
            "exported": exported,
            "skipped_point_labels": skipped_point_labels,
            "skipped_existing": skipped_existing,
        }
