import pytest

from app.entities import QuoteEnquiry


def make_quote_enquiry(**overrides):
    data = {
        'name': 'Aroha Smith',
        'email': 'Aroha.Smith@example.co.nz',
        'phone': '+64 21 123 4567',
        'location': 'Tauranga, Bay of Plenty',
        'client_type': 'homeowner',
        'pool_type': 'fibreglass family pool',
        'message': 'We would like a full design and installation quote for a new pool.',
        'budget_range': '$80k-$120k',
        'timeframe': '3-6 months',
        'site_address': '12 Example Road, Tauranga',
        'preferred_contact_method': 'phone',
    }
    data.update(overrides)
    return QuoteEnquiry(**data)


def test_quote_enquiry_declares_required_fields():
    assert QuoteEnquiry.REQUIRED_FIELDS == (
        'name',
        'email',
        'phone',
        'location',
        'client_type',
        'pool_type',
        'message',
    )


def test_quote_enquiry_accepts_valid_nationwide_pool_installation_lead():
    enquiry = make_quote_enquiry()

    assert enquiry.is_valid()
    assert enquiry.email == 'aroha.smith@example.co.nz'
    assert enquiry.client_type == 'homeowner'
    assert enquiry.location == 'Tauranga, Bay of Plenty'


def test_quote_enquiry_to_dict_contains_required_and_qualification_fields():
    enquiry = make_quote_enquiry()
    payload = enquiry.to_dict()

    assert payload['name'] == 'Aroha Smith'
    assert payload['email'] == 'aroha.smith@example.co.nz'
    assert payload['phone'] == '+64 21 123 4567'
    assert payload['location'] == 'Tauranga, Bay of Plenty'
    assert payload['client_type'] == 'homeowner'
    assert payload['pool_type'] == 'fibreglass family pool'
    assert payload['message']
    assert payload['budget_range'] == '$80k-$120k'
    assert payload['timeframe'] == '3-6 months'
    assert payload['site_address'] == '12 Example Road, Tauranga'
    assert payload['preferred_contact_method'] == 'phone'
    assert payload['created_at']


@pytest.mark.parametrize('field_name', QuoteEnquiry.REQUIRED_FIELDS)
def test_quote_enquiry_rejects_blank_required_fields(field_name):
    with pytest.raises(ValueError, match=f'{field_name} is required'):
        make_quote_enquiry(**{field_name: '   '})


def test_quote_enquiry_rejects_invalid_email():
    with pytest.raises(ValueError, match='email must be a valid email address'):
        make_quote_enquiry(email='not-an-email')


def test_quote_enquiry_rejects_unknown_client_type():
    with pytest.raises(ValueError, match='client_type must be one of'):
        make_quote_enquiry(client_type='tourist')


def test_quote_enquiry_rejects_unknown_preferred_contact_method():
    with pytest.raises(ValueError, match='preferred_contact_method must be one of'):
        make_quote_enquiry(preferred_contact_method='letter')
