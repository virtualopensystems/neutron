# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright 2013 OpenStack Foundation
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#
# @author: Sean M. Collins, sean@coreitpro.com, Comcast #

from neutron.common import constants
from neutron.common import exceptions
from neutron.db import model_base
from neutron.db import models_v2
from neutron.extensions import qos as ext_qos

import sqlalchemy as sa
from sqlalchemy import orm


class QoSNotFound(exceptions.NotFound):
    message = _("QoS %(qos_id)s could not be found")


class QoSPortMappingNotFound(exceptions.NotFound):
    message = _("QoS mapping for port %(port_id)s"
                "and QoS %(qos_id)s could not be found")


class QoSNetworkMappingNotFound(exceptions.NotFound):
    message = _("QoS mapping for network %(net_id)s"
                "and QoS %(qos_id)s could not be found")


class QoS(model_base.BASEV2, models_v2.HasId, models_v2.HasTenant):
    __tablename__ = 'qoses'
    type = sa.Column(sa.Enum(constants.TYPE_QOS_DSCP,
                             constants.TYPE_QOS_RATELIMIT, name='qos_types'))
    description = sa.Column(sa.String(255), nullable=False)
    policies = orm.relationship('QoSPolicy',
                                cascade='all, delete, delete-orphan')
    ports = orm.relationship('PortQoSMapping',
                             cascade='all, delete, delete-orphan')
    networks = orm.relationship('NetworkQoSMapping',
                                cascade='all, delete, delete-orphan')


class QoSPolicy(model_base.BASEV2, models_v2.HasId):
    __tablename__ = 'qos_policies'
    qos_id = sa.Column(sa.String(36),
                       sa.ForeignKey('qoses.id', ondelete='CASCADE'),
                       nullable=False,
                       primary_key=True)
    key = sa.Column(sa.String(255), nullable=False,
                    primary_key=True)
    value = sa.Column(sa.String(255), nullable=False)


class NetworkQoSMapping(model_base.BASEV2):
    network_id = sa.Column(sa.String(36), sa.ForeignKey('networks.id',
                           ondelete='CASCADE'), nullable=False,
                           primary_key=True)
    qos_id = sa.Column(sa.String(36), sa.ForeignKey('qoses.id',
                       ondelete='CASCADE'), nullable=False, primary_key=True)


class PortQoSMapping(model_base.BASEV2):
    port_id = sa.Column(sa.String(36), sa.ForeignKey('ports.id',
                        ondelete='CASCADE'), nullable=False, primary_key=True)
    qos_id = sa.Column(sa.String(36), sa.ForeignKey('qoses.id',
                       ondelete='CASCADE'), nullable=False, primary_key=True)


class QoSDbMixin(ext_qos.QoSPluginBase):

    def _create_qos_dict(self, qos, fields=None):
        res = {'id': qos['id'],
               'tenant_id': qos['tenant_id'],
               'type': qos['type'],
               'description': qos['description'],
               'policies': {}}
        for item in qos.policies:
            res['policies'][item['key']] = item['value']
        return self._fields(res, fields)

    def _db_delete(self, context, item):
        with context.session.begin(subtransactions=True):
            context.session.delete(item)

    def create_qos(self, context, qos):
        self.validate_qos(qos)
        tenant_id = self._get_tenant_id_for_create(context, qos)

        with context.session.begin(subtransactions=True):
            qos_db_item = QoS(type=qos['qos']['type'],
                              description=qos['qos']['description'],
                              tenant_id=tenant_id)
            for k, v in qos['qos']['policies'].iteritems():
                qos_db_item.policies.append(
                    QoSPolicy(qos_id=qos_db_item.id, key=k, value=v))
            context.session.add(qos_db_item)
        return self._create_qos_dict(qos_db_item)

    def create_qos_for_network(self, context, qos_id, network_id):
        with context.session.begin(subtransactions=True):
            db = NetworkQoSMapping(qos_id=qos_id, network_id=network_id)
            context.session.add(db)
        return db.qos_id

    def create_qos_for_port(self, context, qos_id, port_id):
        with context.session.begin(subtransactions=True):
            db = PortQoSMapping(qos_id=qos_id, port_id=port_id)
            context.session.add(db)
        return db.qos_id

    def delete_qos(self, context, id):
        try:
            self._db_delete(context, self._get_by_id(context, QoS, id))
        except orm.exc.NotFound:
            raise QoSNotFound()

    def delete_qos_for_network(self, context, network_id):
        try:
            self._db_delete(context,
                            self._model_query(context,
                                              NetworkQoSMapping)
                            .filter_by(network_id=network_id).one())
        except orm.exc.NoResultFound:
            raise exceptions.NotFound

    def delete_qos_for_port(self, context, port_id):
        try:
            self._db_delete(context,
                            self._model_query(context, PortQoSMapping)
                            .filter_by(port_id=port_id).one())
        except orm.exc.NoResultFound:
            raise QoSPortMappingNotFound()

    def get_mapping_for_network(self, context, network_id):
        try:
            with context.session.begin(subtransactions=True):
                return self._model_query(context, NetworkQoSMapping).filter_by(
                    network_id=network_id).all()
        except orm.exc.NotFound:
            raise QoSNetworkMappingNotFound()

    def get_mapping_for_port(self, context, port_id):
        try:
            with context.session.begin(subtransactions=True):
                return self._model_query(context, PortQoSMapping).filter_by(
                    port_id=port_id).all()
        except orm.exc.NotFound:
            raise QoSPortMappingNotFound()

    def get_qos(self, context, id, fields=None):
        try:
            with context.session.begin(subtransactions=True):
                return self._create_qos_dict(
                    self._get_by_id(context, QoS, id), fields)
        except orm.exc.NotFound:
            raise QoSNotFound()

    def get_qoses(self, context, filters=None, fields=None,
                  sorts=None, limit=None,
                  marker=None, page_reverse=False, default_sg=False):
        marker_obj = self._get_marker_obj(context, 'qos', limit, marker)

        return self._get_collection(context,
                                    QoS,
                                    self._create_qos_dict,
                                    filters=filters, fields=fields,
                                    sorts=sorts,
                                    limit=limit, marker_obj=marker_obj,
                                    page_reverse=page_reverse)

    def update_mapping_for_network(self, context, mapping):
        db = self.get_mapping_for_network(context, mapping.network_id)[0]
        with context.session.begin(subtransactions=True):
            db.update(mapping)

    def update_mapping_for_port(self, context, mapping):
        db = self.get_mapping_for_port(context, mapping.port_id)[0]
        with context.session.begin(subtransactions=True):
            db.update(mapping)

    def update_qos(self, context, id, qos):
        self.validate_qos(qos)
        db = self._get_by_id(context, QoS, id)
        with context.session.begin(subtransactions=True):
            db.policies = []
            for k, v in qos['qos']['policies'].iteritems():
                db.policies.append(
                    QoSPolicy(qos_id=db, key=k, value=v))
            del qos['qos']['policies']
            db.update(qos)
        return self._create_qos_dict(db)

    def validate_qos(self, qos):
        if 'policies' not in qos['qos']:
            raise ext_qos.QoSValidationError()
        qos = qos['qos']
        try:
            validator = getattr(self, 'validate_policy_' + qos['type'])
        except AttributeError:
            raise Exception(_('No validator found for type: %s') % qos['type'])
        validator(qos['policies'])

    def validate_policy_dscp(self, policy):
        if constants.TYPE_QOS_DSCP in policy:
            try:
                dscp = int(policy[constants.TYPE_QOS_DSCP])
                if dscp < 0 or dscp > 63:
                    raise ext_qos.QoSValidationError()
            except ValueError:
                raise ext_qos.QoSValidationError()
        else:
            raise ext_qos.QoSValidationError()
