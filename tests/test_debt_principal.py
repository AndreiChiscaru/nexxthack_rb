from app.game_profile import to_game_profile
from app.profile_mapping import agent_profile_to_profile, missing_fields
from app.agents import profile


def test_statement_uses_explicit_remaining_debt_not_estimated_term():
    result = to_game_profile({'obligatii_recurente': [
        {'descriere': 'Credit existent', 'tip': 'rata credit', 'suma_lunara': 480,
         'sold_ramas': 7020, 'dobanda_anuala': 0.09}]})
    assert result['loans'][0]['principal'] == 7020
    assert result['loans'][0]['apr'] == 0.09


def test_unknown_debt_terms_are_not_invented():
    result = to_game_profile({'obligatii_recurente': [
        {'descriere': 'PayPo', 'tip': 'rata credit', 'suma_lunara': 100}]})
    loan = result['loans'][0]
    assert loan['principal'] is None
    assert loan['apr'] is None
    data = {'bank': {'debts': [{'name': 'PayPo', 'monthly_payment': 100}]}}
    mapped = agent_profile_to_profile(data)
    assert mapped['debts'][0]['remaining'] is None
    assert mapped['debts'][0]['apr'] is None
    assert 'debts.0.remaining' in missing_fields({'data': data})
    assert 'debts.0.apr' in missing_fields({'data': data})
    assert 'Sold rămas credit: PayPo' in profile.missing({'data': data})


def test_explicit_zero_interest_is_preserved():
    mapped = agent_profile_to_profile({'bank': {'debts': [
        {'name': 'PayPo', 'monthly_payment': 100, 'remaining': 600, 'apr': 0}]}})
    assert mapped['debts'] == [{'name': 'PayPo', 'monthly': 100, 'remaining': 600, 'apr': 0}]
