from utils import (
    ensure_output_directory,
    format_timestamp,
    format_transcript,
    get_output_directory,
    get_unique_output_path,
    is_supported_media_file,
)


def test_supported_media_file_is_case_insensitive():
    assert is_supported_media_file("recording.MP3")
    assert not is_supported_media_file("notes.txt")


def test_output_directory_is_next_to_input(tmp_path):
    input_path = tmp_path / "recording.wav"

    assert get_output_directory(input_path) == str(tmp_path / "Whisper_Transcriptions")
    assert ensure_output_directory(input_path) == str(tmp_path / "Whisper_Transcriptions")
    assert (tmp_path / "Whisper_Transcriptions").is_dir()


def test_unique_output_path_avoids_existing_transcripts(tmp_path):
    source_path = tmp_path / "recording.wav"
    output_directory = tmp_path / "Whisper_Transcriptions"
    output_directory.mkdir()
    (output_directory / "recording.txt").touch()
    (output_directory / "recording_1.txt").touch()

    assert get_unique_output_path(output_directory, source_path) == str(
        output_directory / "recording_2.txt"
    )


def test_transcript_format_matches_application_output():
    segments = [
        {"start": 0, "end": 1.234, "text": " Hello "},
        {"start": 1.234, "end": 2, "text": "world"},
    ]

    assert format_timestamp(1.234) == "1.23"
    assert format_transcript(segments) == (
        "[0.00 -> 1.23] Hello\n"
        "[1.23 -> 2.00] world\n"
    )
