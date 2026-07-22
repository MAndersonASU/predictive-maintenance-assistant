"""Reproducible acquisition utilities for governed project datasets."""

from __future__ import annotations

import csv
import hashlib
import shutil
import urllib.error
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
SOURCE_MANIFEST_PATH = PROJECT_ROOT / "data" / "source_manifest.csv"

METROPT_SOURCE_ID = "metropt3_uci"
VERIFIED_SOURCE_STATUS = "downloaded_and_verified"

UCI_DATASET_ID = 791
DOWNLOAD_URL = (
    "https://archive.ics.uci.edu/static/public/791/"
    "metropt%2B3%2Bdataset.zip"
)

ARCHIVE_NAME = "metropt_3_dataset.zip"
ARCHIVE_PATH = RAW_DATA_DIR / ARCHIVE_NAME

DATASET_CSV_NAME = "MetroPT3(AirCompressor).csv"
DATA_DESCRIPTION_NAME = "Data Description_Metro.pdf"
DATASET_CSV_PATH = RAW_DATA_DIR / DATASET_CSV_NAME

EXPECTED_CSV_HEADER = (
    "",
    "timestamp",
    "TP2",
    "TP3",
    "H1",
    "DV_pressure",
    "Reservoirs",
    "Oil_temperature",
    "Motor_current",
    "COMP",
    "DV_eletric",
    "Towers",
    "MPG",
    "LPS",
    "Pressure_switch",
    "Oil_level",
    "Caudal_impulses",
)

EXPECTED_ARCHIVE_MEMBERS = (
    DATASET_CSV_NAME,
    DATA_DESCRIPTION_NAME,
)

CHECKSUM_CHUNK_SIZE = 1024 * 1024
DOWNLOAD_CHUNK_SIZE = 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 60
HTTP_USER_AGENT = "predictive-maintenance-assistant/0.1"


class AcquisitionError(RuntimeError):
    """Raised when governed dataset acquisition cannot be completed safely."""


def ensure_raw_data_dir() -> Path:
    """Create and return the ignored raw-data directory."""

    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return RAW_DATA_DIR


def download_archive(
    url: str = DOWNLOAD_URL,
    destination_path: Path = ARCHIVE_PATH,
    *,
    overwrite: bool = False,
    timeout_seconds: int = REQUEST_TIMEOUT_SECONDS,
) -> Path:
    """Download an archive safely and return its completed local path."""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero")

    destination_path = Path(destination_path)

    if destination_path.exists() and not overwrite:
        raise AcquisitionError(
            f"Destination file already exists: {destination_path}"
        )

    destination_path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = destination_path.with_name(
        f"{destination_path.name}.part"
    )

    if temporary_path.exists():
        temporary_path.unlink()

    request = urllib.request.Request(
        url,
        headers={"User-Agent": HTTP_USER_AGENT},
    )

    bytes_written = 0
    expected_bytes: int | None = None

    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout_seconds,
        ) as response:
            status_code = getattr(response, "status", None)

            if status_code not in (None, 200):
                raise AcquisitionError(
                    f"Unexpected HTTP status {status_code} for {url}"
                )

            content_length = response.headers.get("Content-Length")

            if content_length:
                try:
                    expected_bytes = int(content_length)
                except ValueError:
                    expected_bytes = None

            with temporary_path.open("wb") as destination_handle:
                while True:
                    chunk = response.read(DOWNLOAD_CHUNK_SIZE)

                    if not chunk:
                        break

                    destination_handle.write(chunk)
                    bytes_written += len(chunk)

        if bytes_written == 0:
            raise AcquisitionError(f"Downloaded file is empty: {url}")

        if expected_bytes is not None and bytes_written != expected_bytes:
            raise AcquisitionError(
                "Downloaded byte count does not match "
                f"Content-Length: expected {expected_bytes}, "
                f"received {bytes_written}"
            )

        temporary_path.replace(destination_path)

    except AcquisitionError:
        if temporary_path.exists():
            temporary_path.unlink()
        raise

    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
        OSError,
    ) as error:
        if temporary_path.exists():
            temporary_path.unlink()

        raise AcquisitionError(
            f"Unable to download dataset archive from {url}"
        ) from error

    return destination_path


def calculate_sha256(
    file_path: Path,
    chunk_size: int = CHECKSUM_CHUNK_SIZE,
) -> str:
    """Return the SHA-256 checksum of a local file."""

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")

    if not file_path.exists():
        raise AcquisitionError(f"File does not exist: {file_path}")

    if not file_path.is_file():
        raise AcquisitionError(f"Path is not a file: {file_path}")

    digest = hashlib.sha256()

    with file_path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(chunk_size), b""):
            digest.update(chunk)

    return digest.hexdigest()


def validate_csv_header(
    csv_path: Path = DATASET_CSV_PATH,
    expected_header: tuple[str, ...] = EXPECTED_CSV_HEADER,
) -> tuple[str, ...]:
    """Validate the exact source CSV header and return its columns."""

    if not csv_path.exists():
        raise AcquisitionError(f"CSV file does not exist: {csv_path}")

    if not csv_path.is_file():
        raise AcquisitionError(f"CSV path is not a file: {csv_path}")

    if csv_path.stat().st_size == 0:
        raise AcquisitionError(f"CSV file is empty: {csv_path}")

    try:
        with csv_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as csv_file:
            reader = csv.reader(csv_file)
            header = next(reader, None)

    except (OSError, UnicodeError, csv.Error) as error:
        raise AcquisitionError(
            f"Unable to read CSV header: {csv_path}"
        ) from error

    if header is None:
        raise AcquisitionError(
            f"CSV file does not contain a header: {csv_path}"
        )

    actual_header = tuple(header)

    if actual_header != expected_header:
        raise AcquisitionError(
            "CSV header does not match the governed schema.\n"
            f"Expected: {expected_header}\n"
            f"Actual:   {actual_header}"
        )

    return actual_header


def update_source_manifest(
    checksum: str,
    manifest_path: Path = SOURCE_MANIFEST_PATH,
    source_id: str = METROPT_SOURCE_ID,
    status: str = VERIFIED_SOURCE_STATUS,
) -> Path:
    """Update a governed dataset record after successful verification."""

    normalized_checksum = checksum.strip().lower()

    if (
        len(normalized_checksum) != 64
        or not all(
            character in "0123456789abcdef"
            for character in normalized_checksum
        )
    ):
        raise AcquisitionError(
            "Checksum must be a 64-character SHA-256 hexadecimal value"
        )

    if not manifest_path.exists():
        raise AcquisitionError(
            f"Source manifest does not exist: {manifest_path}"
        )

    if not manifest_path.is_file():
        raise AcquisitionError(
            f"Source manifest path is not a file: {manifest_path}"
        )

    try:
        with manifest_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as manifest_file:
            reader = csv.DictReader(manifest_file)
            fieldnames = reader.fieldnames

            if fieldnames is None:
                raise AcquisitionError(
                    f"Source manifest has no header: {manifest_path}"
                )

            required_fields = {
                "source_id",
                "checksum",
                "status",
            }
            missing_fields = sorted(required_fields - set(fieldnames))

            if missing_fields:
                raise AcquisitionError(
                    "Source manifest is missing required field(s): "
                    + ", ".join(missing_fields)
                )

            rows = list(reader)

    except (OSError, UnicodeError, csv.Error) as error:
        raise AcquisitionError(
            f"Unable to read source manifest: {manifest_path}"
        ) from error

    matching_rows = [
        row
        for row in rows
        if row["source_id"] == source_id
    ]

    if len(matching_rows) != 1:
        raise AcquisitionError(
            f"Expected exactly one manifest record for "
            f"{source_id!r}; found {len(matching_rows)}"
        )

    matching_rows[0]["checksum"] = normalized_checksum
    matching_rows[0]["status"] = status

    temporary_path = manifest_path.with_name(
        f"{manifest_path.name}.part"
    )

    if temporary_path.exists():
        temporary_path.unlink()

    try:
        with temporary_path.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as manifest_file:
            writer = csv.DictWriter(
                manifest_file,
                fieldnames=fieldnames,
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(rows)

        temporary_path.replace(manifest_path)

    except OSError as error:
        if temporary_path.exists():
            temporary_path.unlink()

        raise AcquisitionError(
            f"Unable to update source manifest: {manifest_path}"
        ) from error

    return manifest_path


def validate_archive(
    archive_path: Path,
    expected_members: tuple[str, ...] = EXPECTED_ARCHIVE_MEMBERS,
) -> tuple[str, ...]:
    """Validate a ZIP archive and return its non-directory member names."""

    if not archive_path.exists():
        raise AcquisitionError(f"Archive does not exist: {archive_path}")

    if not archive_path.is_file():
        raise AcquisitionError(
            f"Archive path is not a file: {archive_path}"
        )

    if archive_path.stat().st_size == 0:
        raise AcquisitionError(f"Archive is empty: {archive_path}")

    if not zipfile.is_zipfile(archive_path):
        raise AcquisitionError(
            f"File is not a valid ZIP archive: {archive_path}"
        )

    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            corrupt_member = archive.testzip()

            if corrupt_member is not None:
                raise AcquisitionError(
                    f"Archive contains a corrupted member: {corrupt_member}"
                )

            member_names = tuple(
                member.filename
                for member in archive.infolist()
                if not member.is_dir()
            )

    except zipfile.BadZipFile as error:
        raise AcquisitionError(
            f"Unable to read ZIP archive: {archive_path}"
        ) from error

    member_basenames = {
        PurePosixPath(member_name).name
        for member_name in member_names
    }

    missing_members = sorted(
        expected_member
        for expected_member in expected_members
        if expected_member not in member_basenames
    )

    if missing_members:
        missing_text = ", ".join(missing_members)
        raise AcquisitionError(
            f"Archive is missing expected file(s): {missing_text}"
        )

    return member_names


def extract_expected_members(
    archive_path: Path,
    destination_dir: Path = RAW_DATA_DIR,
    expected_members: tuple[str, ...] = EXPECTED_ARCHIVE_MEMBERS,
    overwrite: bool = False,
) -> tuple[Path, ...]:
    """Safely extract expected files and return their destination paths."""

    member_names = validate_archive(
        archive_path=archive_path,
        expected_members=expected_members,
    )

    matches: dict[str, list[str]] = {
        expected_member: []
        for expected_member in expected_members
    }

    for member_name in member_names:
        basename = PurePosixPath(member_name).name

        if basename in matches:
            matches[basename].append(member_name)

    ambiguous_members = {
        expected_member: matched_names
        for expected_member, matched_names in matches.items()
        if len(matched_names) != 1
    }

    if ambiguous_members:
        details = "; ".join(
            f"{name}: {matched_names}"
            for name, matched_names in ambiguous_members.items()
        )
        raise AcquisitionError(
            f"Archive members cannot be resolved uniquely: {details}"
        )

    destination_dir.mkdir(parents=True, exist_ok=True)
    extracted_paths: list[Path] = []

    with zipfile.ZipFile(archive_path, "r") as archive:
        for expected_member in expected_members:
            archive_member = matches[expected_member][0]
            destination_path = destination_dir / expected_member
            temporary_path = destination_path.with_name(
                f"{destination_path.name}.part"
            )

            if destination_path.exists() and not overwrite:
                raise AcquisitionError(
                    f"Destination file already exists: {destination_path}"
                )

            if temporary_path.exists():
                temporary_path.unlink()

            try:
                with archive.open(archive_member, "r") as source_handle:
                    with temporary_path.open("wb") as destination_handle:
                        shutil.copyfileobj(
                            source_handle,
                            destination_handle,
                        )

                if temporary_path.stat().st_size == 0:
                    raise AcquisitionError(
                        f"Extracted file is empty: {expected_member}"
                    )

                temporary_path.replace(destination_path)

            except Exception as error:
                if temporary_path.exists():
                    temporary_path.unlink()

                if isinstance(error, AcquisitionError):
                    raise

                raise AcquisitionError(
                    f"Unable to extract archive member: {archive_member}"
                ) from error

            extracted_paths.append(destination_path)

    return tuple(extracted_paths)
