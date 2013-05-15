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
from sqlalchemy.orm import exc

from neutron.db import qos_db
from neutron.extensions import qos


class QoSServerRpcMixin(qos_db.QoSDbMixin):

    def _process_create_qos_for_network(self, context, qos_id, network_id):
        super(QoSServerRpcMixin, self).create_qos_for_network(
            context, qos_id, network_id)
        self.notifier.network_qos_updated(context, qos_id, network_id)

    def _process_create_qos_for_port(self, context, qos_id, port_id):
        super(QoSServerRpcMixin, self).create_qos_for_port(
            context, qos_id, port_id)
        self.notifier.port_qos_updated(context, qos_id, port_id)

    def _process_delete_qos_for_network(self, context, qos_id, network_id):
        super(QoSServerRpcMixin, self).delete_qos_for_network(
            context, network_id)
        self.notifier.network_qos_deleted(context, qos_id, network_id)

    def _process_delete_qos_for_port(self, context, qos_id, port_id):
        super(QoSServerRpcMixin, self).delete_qos_for_port(
            context, port_id)
        self.notifier.port_qos_deleted(context, qos_id, port_id)

    def _process_update_mapping_for_network(self, context, mapping):
        super(QoSServerRpcMixin, self).update_mapping_for_network(
            context, mapping)
        self.notifier.network_qos_updated(context,
                                          mapping.qos_id,
                                          mapping.network_id)

    def _process_update_mapping_for_port(self, context, mapping):
        super(QoSServerRpcMixin, self).update_mapping_for_port(
            context, mapping)
        self.notifier.port_qos_updated(context,
                                       mapping.qos_id,
                                       mapping.port_id)

    def update_qos(self, context, id, qos):
        result = super(QoSServerRpcMixin, self).update_qos(context,
                                                           id,
                                                           qos)
        qos_item = self._get_by_id(context, qos_db.QoS, id)
        for port_mapping in qos_item.ports:
            self.notifier.port_qos_updated(context,
                                           id,
                                           port_mapping['port_id'])
        for net_mapping in qos_item.networks:
            self.notifier.network_qos_updated(context,
                                              id,
                                              net_mapping['network_id'])
        return result

    def delete_qos(self, context, id):
        qos_item = self._get_by_id(context, qos_db.QoS, id)
        for port_mapping in qos_item.ports:
            self.notifier.port_qos_deleted(context,
                                           id,
                                           port_mapping['port_id'])

        for net_mapping in qos_item.networks:
            self.notifier.network_qos_deleted(context,
                                              id,
                                              net_mapping['network_id'])
        super(QoSServerRpcMixin, self).delete_qos(context, id)

    def _process_qos_network_update(self, context, network, req_data):
        if qos.QOS not in req_data:
            return
        qos_id = req_data.get(qos.QOS, None)
        mapping = self.get_mapping_for_network(context, network['id'])
        if qos_id and not mapping:
            self._process_create_qos_for_network(context,
                                                 req_data['qos'],
                                                 network['id'])
        elif not qos_id and mapping:
            self._process_delete_qos_for_network(context,
                                                 mapping[0].qos_id,
                                                 network['id'])
        elif qos_id:
            qos_id = req_data['qos']
            mapping = mapping[0]
            mapping.qos_id = qos_id
            self._process_update_mapping_for_network(context, mapping)

    def _process_qos_port_update(self, context, port, req_data):
        if qos.QOS not in req_data:
            return
        qos_id = req_data.get(qos.QOS, None)
        mapping = self.get_mapping_for_port(context, port['id'])

        if qos_id and not mapping:
            self._process_create_qos_for_port(context,
                                              qos_id,
                                              port['id'])
        elif not qos_id and mapping:
            self._process_delete_qos_for_port(context,
                                              mapping[0].qos_id,
                                              port['id'])
        elif qos_id:
            qos_id = req_data['qos']
            mapping = mapping[0]
            mapping.qos_id = qos_id
            self._process_update_mapping_for_port(context, mapping)


class QoSServerRpcCallbackMixin(object):

    def get_policy_for_qos(self, context, **kwargs):
        result = {}
        qos_id = kwargs.get('qos_id')
        query = context.session.query(qos_db.QoS)
        results = query.filter_by(id=qos_id)
        for policy in results.one().policies:
            result[policy['key']] = policy['value']
        return result

    def get_qos_by_network(self, context, **kwargs):
        network_id = kwargs.get('network_id')
        query = context.session.query(qos_db.NetworkQoSMapping)
        try:
            mapping = query.filter_by(network_id=network_id).one()
            return mapping.qos_id
        except exc.NoResultFound:
            return []
