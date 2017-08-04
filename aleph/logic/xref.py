import logging
from pprint import pprint  # noqa
from elasticsearch.helpers import scan
import xlsxwriter
import StringIO

from aleph.core import db, es, es_index, schemata
from aleph.model import Match
from aleph.logic.collections import collection_url
from aleph.logic.entities import entity_url
from aleph.index import TYPE_ENTITY, TYPE_DOCUMENT
from aleph.index.xref import entity_query
from aleph.index.util import unpack_result
from aleph.search import QueryParser, MatchQueryResult

log = logging.getLogger(__name__)


def xref_item(item):
    """Cross-reference an entity or document, given as an indexed document."""
    title = item.get('name') or item.get('title')
    log.info("Xref [%s]: %s", item['$type'], title)

    result = es.search(index=es_index,
                       doc_type=TYPE_ENTITY,
                       body={
                           'query': entity_query(item),
                           'size': 100,
                           '_source': ['collection_id'],
                       })
    results = result.get('hits').get('hits')
    entity_id, document_id = None, None
    if item.get('$type') == TYPE_DOCUMENT:
        document_id = item.get('id')
    else:
        entity_id = item.get('id')
    dq = db.session.query(Match)
    dq = dq.filter(Match.entity_id == entity_id)
    dq = dq.filter(Match.document_id == document_id)
    dq.delete()
    matches = []
    for result in results:
        source = result.get('_source', {})
        obj = Match()
        obj.entity_id = entity_id
        obj.document_id = document_id
        obj.collection_id = item.get('collection_id')
        obj.match_id = result.get('_id')
        obj.match_collection_id = source.get('collection_id')
        obj.score = result.get('_score')
        matches.append(obj)
    db.session.bulk_save_objects(matches)


def xref_collection(collection):
    """Cross-reference all the entities and documents in a collection."""
    log.info("Cross-reference collection: %r", collection)
    query = {
        'query': {
            'term': {'collection_id': collection.id}
        }
    }
    scanner = scan(es,
                   index=es_index,
                   doc_type=[TYPE_ENTITY, TYPE_DOCUMENT],
                   query=query)
    for i, res in enumerate(scanner):
        xref_item(unpack_result(res))
        if i % 1000 == 0 and i != 0:
            db.session.commit()
    db.session.commit()


def make_excel_safe_name(collection):
    name = '%s. %s' % (collection.id, collection.label)
    for char in '[]:*?/\\':
        name = name.replace(char, " ").strip()
    return name[:30]


def generate_matches_sheet(workbook, collection, match_collection, authz):
    from aleph.views.serializers import MatchSchema
    bold = workbook.add_format({'bold': 1})
    link_format = workbook.add_format({
        'font_color': 'blue',
        'underline': 1
    })

    sheet_name = make_excel_safe_name(match_collection)
    sheet = workbook.add_worksheet(sheet_name)
    parser = QueryParser({}, authz, limit=1000)
    q_match = Match.find_by_collection(collection.id, match_collection.id)
    matches = MatchQueryResult({}, q_match, parser=parser, schema=MatchSchema)

    sheet.write(1, 0, 'Score', bold)
    sheet.merge_range(0, 1, 0, 4, collection.label, bold)
    sheet.write(1, 1, 'Name', bold)
    sheet.write(1, 2, 'Type', bold)
    sheet.write(1, 3, 'Country', bold)
    sheet.write(1, 4, 'Source URL', bold)
    sheet.merge_range(0, 5, 0, 7, match_collection.label, bold)
    sheet.write(1, 5, 'Name', bold)
    sheet.write(1, 6, 'Type', bold)
    sheet.write(1, 7, 'Country', bold)

    sheet.freeze_panes(2, 0)
    sheet.autofilter(1, 1, 2 + len(matches.results), 8)
    widths = {}
    for row, result in enumerate(matches.results, 2):
        sheet.write_number(row, 0, int(result.score))
        name = result.entity.get('name')
        ent_url = entity_url(result.entity_id)
        widths[1] = max(widths.get(1, 0), len(name))
        sheet.write_url(row, 1, ent_url, link_format, name)
        schema = schemata.get(result.entity['schema'])
        sheet.write_string(row, 2, schema.label)
        countries = ', '.join(result.entity.get('countries', []))
        sheet.write_string(row, 3, countries.upper())
        ent_props = result.entity.get('properties', {})
        source_url = ', '.join(ent_props.get('sourceUrl'))
        sheet.write_string(row, 4, source_url)

        name = result.match.get('name')
        match_url = entity_url(result.match_id)
        widths[5] = max(widths.get(5, 0), len(name))
        sheet.write_url(row, 5, match_url, link_format, name)
        schema = schemata.get(result.match['schema'])
        sheet.write_string(row, 6, schema.label)
        countries = ', '.join(result.match.get('countries', []))
        sheet.write_string(row, 7, countries.upper())

    for idx, max_len in widths.items():
        max_len = min(70, max(7, max_len + 1))
        sheet.set_column(idx, idx, float(max_len))

    return sheet_name


def generate_excel(collection, authz):
    output = StringIO.StringIO()
    workbook = xlsxwriter.Workbook(output)
    link_format = workbook.add_format({
        'font_color': 'blue',
        'underline': 1
    })

    # Write the summary worksheet (Collection names and count)
    sheet = workbook.add_worksheet('Summary')
    bold = workbook.add_format({'bold': 1})
    sheet.write(0, 0, 'Collection', bold)
    sheet.write(0, 1, 'Matches', bold)
    sheet.write(0, 2, 'Details', bold)
    sheet.freeze_panes(1, 0)

    # Query for all the collections with matches
    collections = Match.group_by_collection(collection.id, authz=authz)
    max_label = 0
    for row, result in enumerate(collections, 1):
        url = collection_url(result.collection.id)
        sheet.write_url(row, 0, url, link_format, result.collection.label)
        max_label = max(max_label, len(result.collection.label))
        sheet.set_column(0, 0, float(max_label))
        sheet.write_number(row, 1, result.matches)
        name = generate_matches_sheet(workbook,
                                      collection,
                                      result.collection,
                                      authz)
        url = "internal:'%s'!B3" % name
        sheet.write_url(row, 2, url, link_format, 'See matches')

    workbook.close()
    output.seek(0)
    return output
