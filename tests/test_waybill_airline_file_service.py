import pytest
from fastapi import HTTPException

from app.services.waybill_airline_file_service import (
    WaybillAirlineFileService,
    extract_air_waybill_candidates,
)


def test_extract_air_waybill_candidates_supports_common_pdf_formats() -> None:
    text = """
    MAWB: 176-60198191
    Air Waybill No. 176 6019 8191
    BL 78484192500
    """

    assert extract_air_waybill_candidates(text) == ["176-60198191", "784-84192500"]


def test_extract_air_waybill_candidates_ignores_duplicates() -> None:
    assert extract_air_waybill_candidates("072-74118542 07274118542") == ["072-74118542"]


def test_airline_file_pdf_validation_rejects_non_pdf_extension() -> None:
    service = WaybillAirlineFileService.__new__(WaybillAirlineFileService)

    with pytest.raises(HTTPException) as exc_info:
        service._validate_pdf("airline-file.txt", b"%PDF-1.7")

    assert exc_info.value.detail == "airline_file_must_be_pdf"


def test_airline_file_pdf_validation_rejects_invalid_pdf_header() -> None:
    service = WaybillAirlineFileService.__new__(WaybillAirlineFileService)

    with pytest.raises(HTTPException) as exc_info:
        service._validate_pdf("airline-file.pdf", b"not a pdf")

    assert exc_info.value.detail == "airline_file_invalid_pdf_header"
