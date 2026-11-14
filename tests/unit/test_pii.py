from data.pipeline.pii import mask_pii


def test_masks_contact_details() -> None:
    text = "Mail jo.doe+x@mail.co.uk, call +1 (555) 123-4567, see https://x.io/a or ping @jodoe"
    assert mask_pii(text) == "Mail [EMAIL], call [PHONE], see [URL] or ping [HANDLE]"


def test_keeps_dates_money_and_plain_text() -> None:
    text = "Start 2024-02-17, budget $1,500, 3 to 6 months, Python 3.11"
    assert mask_pii(text) == text
