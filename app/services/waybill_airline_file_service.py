from __future__ import annotations

import hashlib
import logging
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from app.core.platform_patch import patch_platform_wmi

patch_platform_wmi()

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import bad_request, not_found
from app.models import AirWaybill, User, WaybillAirlineFile
from app.schemas.waybill import (
    WaybillAirlineFileBatchFailure,
    WaybillAirlineFileBatchSuccess,
    WaybillAirlineFileBatchUploadResult,
    WaybillAirlineFileOut,
)
from app.services.permission_service import PermissionService
from app.services.waybill_service import WaybillService

logger = logging.getLogger(__name__)

AIR_WAYBILL_CANDIDATE_PATTERN = re.compile(r"(?<!\d)(\d{3})[\s\-]*(\d{4})[\s\-]*(\d{4})(?!\d)")
PDF_HEADER = b"%PDF"


class AirlineFileRecognitionError(Exception):
    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code
        self.message = message


@dataclass
class AirlineFileUploadOutcome:
    file: WaybillAirlineFile
    replaced_existing: bool


@dataclass
class AirlineFileDownload:
    file: WaybillAirlineFile
    path: Path


def extract_air_waybill_candidates(text: str | None) -> list[str]:
    if not text:
        return []
    candidates: list[str] = []
    seen: set[str] = set()
    normalized_text = text.replace("\u3000", " ")
    for match in AIR_WAYBILL_CANDIDATE_PATTERN.finditer(normalized_text):
        candidate = f"{match.group(1)}-{match.group(2)}{match.group(3)}"
        if candidate in seen:
            continue
        seen.add(candidate)
        candidates.append(candidate)
    return candidates


def extract_pdf_air_waybill_candidates(content: bytes) -> tuple[list[str], str | None]:
    text_candidates = _extract_candidates_from_text_layer(content)
    if text_candidates:
        return text_candidates, "text"
    ocr_candidates = _extract_candidates_with_ocr(content)
    if ocr_candidates:
        return ocr_candidates, "ocr"
    return [], None


def _dedupe_candidates(groups: list[list[str]]) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for candidate in group:
            if candidate in seen:
                continue
            seen.add(candidate)
            candidates.append(candidate)
    return candidates


def _extract_candidates_from_text_layer(content: bytes) -> list[str]:
    try:
        import pdfplumber
    except Exception as exc:  # pragma: no cover - depends on optional runtime package
        logger.info("pdfplumber unavailable for airline file recognition: %s", exc)
        return []

    try:
        with pdfplumber.open(BytesIO(content)) as pdf:
            if not pdf.pages:
                return []
            page = pdf.pages[0]
            width = float(page.width)
            height = float(page.height)
            regions = [
                (width * 0.50, 0, width, height * 0.28),
                (0, 0, width, height * 0.24),
            ]
            candidate_groups: list[list[str]] = []
            for bbox in regions:
                try:
                    text = page.crop(bbox).extract_text(x_tolerance=2, y_tolerance=3) or ""
                except Exception:
                    text = ""
                candidate_groups.append(extract_air_waybill_candidates(text))
            candidate_groups.append(extract_air_waybill_candidates(page.extract_text(x_tolerance=2, y_tolerance=3) or ""))
            return _dedupe_candidates(candidate_groups)
    except Exception as exc:
        logger.warning("Failed to extract text layer from airline PDF: %s", exc)
        return []


def _extract_candidates_with_ocr(content: bytes) -> list[str]:
    if shutil.which("tesseract") is None:
        raise AirlineFileRecognitionError(
            "ocr_runtime_unavailable",
            "OCR runtime tesseract is not installed on the server",
        )
    try:
        import pypdfium2 as pdfium
        import pytesseract
    except Exception as exc:
        raise AirlineFileRecognitionError(
            "ocr_runtime_unavailable",
            f"OCR dependencies are unavailable: {exc}",
        ) from exc

    try:
        pdf = pdfium.PdfDocument(content)
        if len(pdf) == 0:
            return []
        page = pdf[0]
        image = page.render(scale=3).to_pil()
        width, height = image.size
        regions = [
            image.crop((int(width * 0.50), 0, width, int(height * 0.30))),
            image.crop((0, 0, width, int(height * 0.26))),
        ]
        candidate_groups: list[list[str]] = []
        for region in regions:
            gray = region.convert("L")
            threshold = gray.point(lambda value: 0 if value < 180 else 255)
            text = pytesseract.image_to_string(
                threshold,
                config="--psm 6 -c tessedit_char_whitelist=0123456789- ",
            )
            candidate_groups.append(extract_air_waybill_candidates(text))
        page.close()
        pdf.close()
        return _dedupe_candidates(candidate_groups)
    except AirlineFileRecognitionError:
        raise
    except Exception as exc:
        raise AirlineFileRecognitionError("ocr_failed", f"OCR failed: {exc}") from exc


class WaybillAirlineFileService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = WaybillService(db).repo
        self.storage_root = Path(settings.airline_file_storage_dir).resolve()

    def upload_for_waybill(
        self,
        waybill_id: int,
        file_name: str,
        content: bytes,
        content_type: str | None,
        current_user: User,
        *,
        extracted_waybill_no: str | None = None,
        extraction_method: str | None = "direct",
    ) -> AirlineFileUploadOutcome:
        PermissionService.assert_waybill_write(current_user)
        WaybillService(self.db).get_visible(waybill_id, current_user)
        self._validate_pdf(file_name, content)
        return self._replace_file(
            waybill_id,
            file_name,
            content,
            content_type,
            current_user,
            extracted_waybill_no=extracted_waybill_no,
            extraction_method=extraction_method,
        )

    def batch_upload(
        self,
        files: list[tuple[str, bytes, str | None]],
        current_user: User,
    ) -> WaybillAirlineFileBatchUploadResult:
        PermissionService.assert_waybill_write(current_user)
        successes: list[WaybillAirlineFileBatchSuccess] = []
        failures: list[WaybillAirlineFileBatchFailure] = []

        for file_name, content, content_type in files:
            extracted_waybill_no: str | None = None
            try:
                self._validate_pdf(file_name, content)
                candidates, extraction_method = extract_pdf_air_waybill_candidates(content)
                if not candidates:
                    failures.append(
                        WaybillAirlineFileBatchFailure(
                            file_name=file_name,
                            error_code="waybill_not_found_or_unrecognized",
                            message="未能从 PDF 首页识别到已存在的正式提单号",
                        )
                    )
                    continue

                matched_waybills = self._match_existing_waybills(candidates)
                if len(matched_waybills) == 0:
                    extracted_waybill_no = candidates[0]
                    failures.append(
                        WaybillAirlineFileBatchFailure(
                            file_name=file_name,
                            error_code="waybill_not_found_or_unrecognized",
                            message=f"识别到 {extracted_waybill_no}，但系统中没有对应正式提单",
                            extracted_waybill_no=extracted_waybill_no,
                        )
                    )
                    continue
                if len(matched_waybills) > 1:
                    failures.append(
                        WaybillAirlineFileBatchFailure(
                            file_name=file_name,
                            error_code="ambiguous_waybill_no",
                            message="PDF 中识别到多个系统内存在的提单号，无法自动判断绑定目标",
                            extracted_waybill_no=", ".join(item.waybill_no for item in matched_waybills),
                        )
                    )
                    continue

                waybill = matched_waybills[0]
                extracted_waybill_no = waybill.waybill_no
                outcome = self._replace_file(
                    waybill.id,
                    file_name,
                    content,
                    content_type,
                    current_user,
                    extracted_waybill_no=extracted_waybill_no,
                    extraction_method=extraction_method,
                )
                successes.append(
                    WaybillAirlineFileBatchSuccess(
                        file_name=file_name,
                        waybill_id=waybill.id,
                        waybill_no=waybill.waybill_no,
                        extracted_waybill_no=extracted_waybill_no,
                        extraction_method=extraction_method,
                        replaced_existing=outcome.replaced_existing,
                        airline_file=WaybillAirlineFileOut.model_validate(outcome.file),
                    )
                )
            except AirlineFileRecognitionError as exc:
                failures.append(
                    WaybillAirlineFileBatchFailure(
                        file_name=file_name,
                        error_code=exc.error_code,
                        message=exc.message,
                        extracted_waybill_no=extracted_waybill_no,
                    )
                )
            except HTTPException as exc:
                failures.append(
                    WaybillAirlineFileBatchFailure(
                        file_name=file_name,
                        error_code=str(exc.detail),
                        message=str(exc.detail),
                        extracted_waybill_no=extracted_waybill_no,
                    )
                )
            except Exception as exc:  # pragma: no cover - defensive per-file isolation
                logger.exception("Failed to upload airline file %s", file_name)
                self.db.rollback()
                failures.append(
                    WaybillAirlineFileBatchFailure(
                        file_name=file_name,
                        error_code="airline_file_upload_failed",
                        message=str(exc),
                        extracted_waybill_no=extracted_waybill_no,
                    )
                )

        return WaybillAirlineFileBatchUploadResult(
            success_count=len(successes),
            failed_count=len(failures),
            successes=successes,
            failures=failures,
        )

    def get_download(self, waybill_id: int, current_user: User) -> AirlineFileDownload:
        waybill = WaybillService(self.db).get_visible(waybill_id, current_user)
        airline_file = waybill.airline_file or self.db.scalar(
            select(WaybillAirlineFile).where(WaybillAirlineFile.waybill_id == waybill_id)
        )
        if not airline_file:
            raise not_found("airline_file_not_found")
        path = Path(airline_file.stored_file_path)
        if not path.exists():
            raise not_found("airline_file_missing_on_disk")
        return AirlineFileDownload(file=airline_file, path=path)

    def delete_for_waybill(self, waybill_id: int, current_user: User) -> None:
        PermissionService.assert_waybill_write(current_user)
        waybill = WaybillService(self.db).get_visible(waybill_id, current_user)
        airline_file = waybill.airline_file or self.db.scalar(
            select(WaybillAirlineFile).where(WaybillAirlineFile.waybill_id == waybill_id)
        )
        if not airline_file:
            raise not_found("airline_file_not_found")
        stored_path = airline_file.stored_file_path
        self.db.delete(airline_file)
        self.db.commit()
        self._safe_unlink(stored_path)

    def _validate_pdf(self, file_name: str, content: bytes) -> None:
        if not file_name.lower().endswith(".pdf"):
            raise bad_request("airline_file_must_be_pdf")
        if not content:
            raise bad_request("airline_file_empty")
        if not content.lstrip().startswith(PDF_HEADER):
            raise bad_request("airline_file_invalid_pdf_header")

    def _match_existing_waybills(self, candidates: list[str]) -> list[AirWaybill]:
        matched: list[AirWaybill] = []
        seen_ids: set[int] = set()
        for candidate in candidates:
            waybill = self.repo.get_by_no(candidate)
            if not waybill or waybill.id in seen_ids:
                continue
            seen_ids.add(waybill.id)
            matched.append(waybill)
        return matched

    def _replace_file(
        self,
        waybill_id: int,
        file_name: str,
        content: bytes,
        content_type: str | None,
        current_user: User,
        *,
        extracted_waybill_no: str | None,
        extraction_method: str | None,
    ) -> AirlineFileUploadOutcome:
        stored_path = self._store_file(waybill_id, file_name, content)
        file_hash = hashlib.sha256(content).hexdigest()
        existing = self.db.scalar(select(WaybillAirlineFile).where(WaybillAirlineFile.waybill_id == waybill_id))
        old_path = existing.stored_file_path if existing else None
        replaced_existing = existing is not None
        record = existing or WaybillAirlineFile(waybill_id=waybill_id)

        record.original_file_name = Path(file_name).name or "airline-file.pdf"
        record.stored_file_path = str(stored_path)
        record.file_hash = file_hash
        record.file_size = len(content)
        record.content_type = content_type or "application/pdf"
        record.extracted_waybill_no = extracted_waybill_no
        record.extraction_method = extraction_method
        record.uploaded_by = current_user.id
        record.uploaded_at = datetime.now(timezone.utc)

        self.db.add(record)
        try:
            self.db.commit()
            self.db.refresh(record)
        except Exception:
            self.db.rollback()
            self._safe_unlink(stored_path)
            raise

        if old_path and str(stored_path) != old_path:
            self._safe_unlink(old_path)
        return AirlineFileUploadOutcome(file=record, replaced_existing=replaced_existing)

    def _store_file(self, waybill_id: int, file_name: str, content: bytes) -> Path:
        file_hash = hashlib.sha256(content).hexdigest()
        safe_name = self._safe_file_name(file_name)
        target_dir = self.storage_root / str(waybill_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{file_hash[:16]}-{safe_name}"
        target_path.write_bytes(content)
        return target_path

    def _safe_file_name(self, file_name: str) -> str:
        name = Path(file_name).name or "airline-file.pdf"
        for char in '<>:"/\\|?*':
            name = name.replace(char, "_")
        if not name.lower().endswith(".pdf"):
            name = f"{name}.pdf"
        if len(name) > 140:
            stem = Path(name).stem[:120]
            name = f"{stem}.pdf"
        return name

    def _safe_unlink(self, path: str | Path) -> None:
        try:
            Path(path).unlink(missing_ok=True)
        except Exception as exc:
            logger.warning("Failed to delete airline file %s: %s", path, exc)
