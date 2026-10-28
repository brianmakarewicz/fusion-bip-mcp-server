"""BIP artifact builders.

These functions turn a simple request (SQL + column names) into the exact data
model (.xdm) XML Oracle BIP expects.
"""

from __future__ import annotations

import re

from .errors import FusionToolError

_COLUMN = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")


def check_columns(sql: str, columns: list[str]) -> None:
    """Reject column lists that BI Publisher would silently turn into empty tags.

    Each name must be an upper-case identifier, appear once, and appear in the SQL
    as a word (normally its alias). A name that never appears in the SQL cannot
    match a SELECT column, and BIP would return it empty on every row.
    """
    if not columns:
        raise FusionToolError("columns is empty: list the alias of every SELECT column")
    bad = [c for c in columns if not _COLUMN.match(c)]
    if bad:
        raise FusionToolError(
            f"Invalid column name(s) {bad}: use upper-case letters, digits and underscores, "
            "starting with a letter, and alias each SELECT column to that name")
    dupes = sorted({c for c in columns if columns.count(c) > 1})
    if dupes:
        raise FusionToolError(f"Duplicate column name(s) {dupes}")
    missing = [c for c in columns if not re.search(rf"(?<![A-Z0-9_$#]){c}(?![A-Z0-9_$#])", sql, re.I)]
    if missing:
        raise FusionToolError(
            f"Column(s) {missing} do not appear in the SQL. Each name in columns must be the "
            "alias of a SELECT column (e.g. SELECT VENDOR_NAME AS SUPPLIER_NAME ...)")


def build_data_model_xml(sql: str, columns: list[str]) -> str:
    """Build a BIP data model (.xdm) that runs one SELECT and tags each column.

    The SQL goes in a CDATA block; each column becomes an upper-case element in a
    single group. Output uses upper-case tags and drops the rowset wrapper.
    """
    check_columns(sql, columns)
    if "]]>" in sql:
        # BI Publisher rejects this sequence in a data model's SQL however it is escaped.
        raise FusionToolError("The SQL contains ']]>', which BI Publisher cannot accept; "
                              "write it as ']]' || '>' instead")
    elems = "".join(
        f'<element name="{c}" value="{c}" dataType="xsd:string" tagName="{c}"/>'
        for c in columns
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<dataModel xmlns="http://xmlns.oracle.com/oxp/xmlp" version="2.1" '
        'defaultDataSourceRef="ApplicationDB_FSCM">'
        '<dataProperties><property name="include_rowsettag" value="false"/>'
        '<property name="xml_tag_case" value="upper"/></dataProperties>'
        '<dataSets><dataSet name="Q" type="complex">'
        f'<sql dataSourceRef="ApplicationDB_FSCM"><![CDATA[{sql}]]></sql></dataSet></dataSets>'
        '<output rootName="DATA_DS" uniqueRowName="false"><nodeList name="data-structure">'
        f'<dataStructure tagName="DATA_DS"><group name="G_1" label="G_1" source="Q">{elems}'
        '</group></dataStructure></nodeList></output>'
        '<eventTriggers/><lexicals/><parameters/><valueSets/><bursting/></dataModel>'
    )