"""BIP artifact builders — the transform IP that never ships to the client.

These functions turn a simple request (SQL + column names) into the exact data
model (.xdm) XML Oracle BIP expects. In the hosted product these run only on the server, so a customer sends
plain JSON and never sees how the XML is assembled, how parameters bind, or how
nested queries are wired. This module is the single source of truth; both the
hosted executors and the local stdio client build artifacts from here.
"""

from __future__ import annotations


def build_data_model_xml(sql: str, columns: list[str]) -> str:
    """Build a BIP data model (.xdm) that runs one SELECT and tags each column.

    The SQL goes in a CDATA block; each column becomes an upper-case element in a
    single group. Output uses upper-case tags and drops the rowset wrapper.
    """
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