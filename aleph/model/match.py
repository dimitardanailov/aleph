import logging
# from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import aliased

from aleph.core import db
from aleph.model.common import IdModel, DatedModel

log = logging.getLogger(__name__)


class Match(db.Model, IdModel, DatedModel):
    entity_id = db.Column(db.String(64))
    document_id = db.Column(db.BigInteger())
    collection_id = db.Column(db.Integer,
                              db.ForeignKey('collection.id'),
                              index=True)
    match_id = db.Column(db.String(64))
    match_collection_id = db.Column(db.Integer,
                                    db.ForeignKey('collection.id'),
                                    index=True)
    score = db.Column(db.Float(), nullable=True)

    @classmethod
    def find_by_collection(cls, collection_id, other_id):
        q = Match.all()
        q = q.filter(Match.collection_id == collection_id)
        q = q.filter(Match.document_id == None)  # noqa
        q = q.filter(Match.match_collection_id == other_id)
        q = q.order_by(Match.score.desc())
        return q

    @classmethod
    def group_by_collection(cls, collection_id, authz=None):
        from aleph.model import Collection, Permission
        cnt = func.count(Match.id).label('matches')
        parent = Match.collection_id.label('parent')
        coll = aliased(Collection, name='collection')
        q = db.session.query(cnt, parent)
        q = q.filter(Match.collection_id == collection_id)
        q = q.filter(Match.document_id == None)  # noqa
        q = q.filter(Match.match_collection_id != collection_id)
        q = q.join(coll, Match.match_collection_id == coll.id)
        if authz is not None and not authz.is_admin:
            q = q.join(Permission,
                       Match.match_collection_id == Permission.collection_id)
            q = q.filter(Permission.deleted_at == None)  # noqa
            q = q.filter(Permission.read == True)  # noqa
            q = q.filter(Permission.role_id.in_(authz.roles))
        q = q.add_entity(coll)
        q = q.group_by(coll, parent)
        q = q.order_by(cnt.desc())
        return q

    def __repr__(self):
        return 'Match(%r, %r, %r, %r)' % (self.entity_id,
                                          self.document_id,
                                          self.match_id,
                                          self.score)
