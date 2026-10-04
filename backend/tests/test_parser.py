from datetime import date

import pytest

from app.services.parser import StatementError, parse_statement, with_fingerprints

from .conftest import SAMPLE


def test_hdfc_statement_with_preamble():
    txns = parse_statement("statement.csv", SAMPLE.read_bytes())
    assert len(txns) == 19
    salary = txns[0]
    assert salary.date == date(2026, 9, 1)
    assert salary.amount == 92000.00
    assert txns[1].amount == -486.00  # withdrawals are negative


def test_sbi_style_columns():
    csv = (b"Txn Date,Value Date,Description,Ref No./Cheque No.,Debit,Credit,Balance\n"
           b"5 Sep 2026,5 Sep 2026,TO TRANSFER-UPI/DR/1234/ZOMATO/,TRF,\"1,250.50\",,1000\n"
           b"6 Sep 2026,6 Sep 2026,BY TRANSFER-NEFT SALARY,TRF,,50000,51000\n")
    txns = parse_statement("sbi.csv", csv)
    assert [t.amount for t in txns] == [-1250.50, 50000.0]
    assert txns[0].date == date(2026, 9, 5)


def test_single_amount_column_with_type():
    csv = b"Date,Details,Amount,Type\n2026-09-03,Netflix,649,DR\n2026-09-04,Refund,100,CR\n"
    assert [t.amount for t in parse_statement("x.csv", csv)] == [-649.0, 100.0]


def test_repeated_rows_get_distinct_fingerprints():
    csv = b"Date,Details,Amount\n03/09/2026,CHAI,-20\n03/09/2026,CHAI,-20\n"
    pairs = with_fingerprints(parse_statement("x.csv", csv))
    assert len({fp for _, fp in pairs}) == 2


def test_rejects_garbage():
    with pytest.raises(StatementError):
        parse_statement("x.csv", b"hello,world\n1,2\n")
    with pytest.raises(StatementError):
        parse_statement("x.docx", b"")
