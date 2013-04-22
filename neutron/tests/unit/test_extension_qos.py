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

import contextlib

import webob.exc

from neutron.api.v2 import attributes as attr
from neutron.db import db_base_plugin_v2
from neutron.db import qos_db
from neutron.extensions import qos as ext_qos
from neutron.tests.unit import test_db_plugin


DB_PLUGIN_KLASS = ('neutron.tests.unit.test_extension_qos.'
                   'QoSTestPlugin')

SAMPLE_QOS = {'type': 'dscp',
              'description': 'test policy',
              'policies': {'dscp': '28'}}

SAMPLE_UPDATE_QOS = {'type': 'dscp',
                     'description': 'af31 policy',
                     'policies': {'dscp': '26'}}

SAMPLE_INVALID_QOS = {'type': 'dscp', 'description':
                      'sample invalid polciy',
                      'policies': {'dscp': '900'}}


class QoSTestExtensionManager(object):

    def get_resources(self):
        return ext_qos.Qos.get_resources()

    def get_actions(self):
        return []

    def get_request_extensions(self):
        return []


class QoSTestCase(test_db_plugin.NeutronDbPluginV2TestCase):

    def _create_qos(self, qos_type, description, policy):
        data = {'qos': {'policies': policy,
                        'tenant_id': 'test_tenant',
                        'description': description,
                        'type': qos_type}
                }

        qos_req = self.new_create_request('qoses', data)
        return qos_req.get_response(self.ext_api)

    def _make_qos(self, qos):
        res = self._create_qos(qos['type'], qos['description'],
                               qos['policies'])
        if res.status_int >= 400:
            raise webob.exc.HTTPClientError(code=res.status_int)
        return self.deserialize(self.fmt, res)

    @contextlib.contextmanager
    def qos(self, policy, no_delete=False):
        qos = self._make_qos(policy)
        try:
            yield qos
        finally:
            if not no_delete:
                self._delete('qoses', qos['qos']['id'])


class QoSTestPlugin(db_base_plugin_v2.NeutronDbPluginV2,
                    qos_db.QoSDbMixin):
    """Test plugin that implements necessary calls on create/delete port
    for associating ports with a QoS policy
    """

    supported_extension_aliases = ["quality-of-service"]

    def get_networks(self, context, filters=None, fields=None,
                     sorts=None, limit=None, marker=None,
                     page_reverse=None):
        neutron_networks = super(QoSTestPlugin, self).get_networks(
            context, filters, sorts=sorts, limit=limit, marker=marker,
            page_reverse=page_reverse)
        if neutron_networks:
            for network in neutron_networks:
                mapping = self.get_mapping_for_network(context, network['id'])
                if mapping:
                    network[ext_qos.QOS] = mapping[0].qos_id
        return neutron_networks

    def get_ports(self, context, filters=None, fields=None,
                  sorts=[], limit=None, marker=None,
                  page_reverse=False):
        neutron_lports = super(QoSTestPlugin, self).get_ports(
            context, filters, sorts=sorts, limit=limit, marker=marker,
            page_reverse=page_reverse)
        if neutron_lports:
            for port in neutron_lports:
                mapping = self.get_mapping_for_port(context, port['id'])
                if mapping:
                    port[ext_qos.QOS] = mapping[0].qos_id
        return neutron_lports

    def update_port(self, context, id, port):
        qos_id = attr.is_attr_set(port['port'].get(ext_qos.QOS))
        mapping = self.get_mapping_for_port(context, id)
        if qos_id and not mapping:
            self.create_qos_for_port(context, port['port']['qos'], id)
        elif not qos_id and mapping:
            self.delete_qos_for_port(context, id)
        else:
            qos_id = port['port']['qos']
            mapping = mapping[0]
            mapping.qos_id = port['port']['qos']
            self.update_mapping_for_port(context, mapping)
        port = super(QoSTestPlugin, self).update_port(context, id, port)
        mapping = self.get_mapping_for_port(context, id)
        if mapping:
            port[ext_qos.QOS] = mapping[0].qos_id
        return port

    def update_network(self, context, id, network):
        qos_id = attr.is_attr_set(network['network'].get(ext_qos.QOS))
        mapping = self.get_mapping_for_network(context, id)
        if qos_id and not mapping:
            self.create_qos_for_network(context, network['network']['qos'], id)
        elif not qos_id and mapping:
            self.delete_qos_for_network(context, id)
        else:
            qos_id = network['network']['qos']
            mapping = mapping[0]
            mapping.qos_id = qos_id
            self.update_mapping_for_network(context, mapping)
        network = super(QoSTestPlugin, self).update_network(context,
                                                            id, network)
        mapping = self.get_mapping_for_network(context, id)
        if mapping:
            network[ext_qos.QOS] = mapping[0].qos_id
        return network


class QoSDBTestCase(QoSTestCase):
    def setUp(self, plugin=None, ext_mgr=None):
        self.default_qos = SAMPLE_QOS
        self.update_qos = SAMPLE_UPDATE_QOS
        self.invalid_policy = SAMPLE_INVALID_QOS
        plugin = plugin or DB_PLUGIN_KLASS
        ext_mgr = ext_mgr or QoSTestExtensionManager()
        super(QoSDBTestCase, self).setUp(plugin=plugin, ext_mgr=ext_mgr)

    def tearDown(self):
        super(QoSDBTestCase, self).tearDown()


class TestQoS(QoSDBTestCase):

    def test_add_mapping_to_network(self):
        with self.network() as n:
            with self.qos(self.default_qos) as qos:
                data = {'network': {ext_qos.QOS: qos['qos']['id']}}
                req = self.new_update_request('networks', data,
                                              n['network']['id'])
                res = self.deserialize(self.fmt, req.get_response(self.api))
                self.assertEqual(res['network'][ext_qos.QOS], qos['qos']['id'])

    def test_add_mapping_to_port(self):
        with self.network() as n:
            with self.subnet(n):
                with self.qos(self.default_qos) as qos:
                    res = self._create_port(self.fmt, n['network']['id'])
                    port = self.deserialize(self.fmt, res)
                    data = {'port': {'name': port['port']['name'],
                                     ext_qos.QOS: qos['qos']['id']}}
                    req = self.new_update_request('ports', data,
                                                  port['port']['id'])
                    res = self.deserialize(self.fmt,
                                           req.get_response(self.api))
                    self.assertEqual(res['port'][ext_qos.QOS],
                                     qos['qos']['id'])
                    self._delete('ports', res['port']['id'])

    def test_create_qos(self):
        with self.qos(self.default_qos) as qos:
            self.assertEqual(qos['qos']['policies'],
                             self.default_qos['policies'])
            self.assertIsNotNone(qos['qos']['id'])

    def test_delete_mapping_for_network(self):
        with self.network() as n:
            with self.subnet(n):
                with self.qos(self.default_qos) as qos:
                    data = {'network': {ext_qos.QOS: qos['qos']['id']}}
                    req = self.new_update_request('networks', data,
                                                  n['network']['id'])
                    res = self.deserialize(self.fmt,
                                           req.get_response(self.api))
                    self.assertEqual(res['network'][ext_qos.QOS],
                                     qos['qos']['id'])
                    del data['network'][ext_qos.QOS]
                    req = self.new_update_request('networks',
                                                  data,
                                                  n['network']['id'])
                    res = self.deserialize(self.fmt,
                                           req.get_response(self.api))
                    self.assertNotIn(ext_qos.QOS, res['network'])

    def test_delete_mapping_for_port(self):
        with self.network() as n:
            with self.subnet(n):
                with self.qos(self.default_qos) as qos:
                    res = self._create_port(self.fmt, n['network']['id'])
                    port = self.deserialize(self.fmt, res)
                    data = {'port': {'fixed_ips': port['port']['fixed_ips'],
                                     'name': port['port']['name'],
                                     ext_qos.QOS: qos['qos']['id']}}
                    req = self.new_update_request('ports', data,
                                                  port['port']['id'])
                    res = self.deserialize(self.fmt,
                                           req.get_response(self.api))
                    del data['port'][ext_qos.QOS]
                    req = self.new_update_request('ports', data,
                                                  port['port']['id'])
                    res = self.deserialize(self.fmt, req.get_response(
                                           self.api))
                    self.assertNotIn(ext_qos.QOS, res['port'])
                self._delete('ports', res['port']['id'])

    def test_get_network_qos(self):
        with self.network() as n:
            with self.qos(self.default_qos) as qos:
                data = {'network': {ext_qos.QOS: qos['qos']['id']}}
                req = self.new_update_request('networks', data,
                                              n['network']['id'])
                res = req.get_response(self.api)
                req = self.new_list_request('networks')
                res = req.get_response(self.api)
                networks = self.deserialize(self.fmt, res)
                network = networks['networks'][0]
                self.assertIsNotNone(network[ext_qos.QOS])

    def test_get_port_qos(self):
        with self.network() as n:
            with self.subnet(n):
                with self.qos(self.default_qos) as qos:
                    req = self._create_port(self.fmt, n['network']['id'])
                    port = self.deserialize(self.fmt, req)
                    data = {'port': {'name': port['port']['name'],
                                     ext_qos.QOS: qos['qos']['id']}}
                    req = self.new_update_request('ports', data,
                                                  port['port']['id'])
                    res = req.get_response(self.api)
                    req = self.new_list_request('ports')
                    res = req.get_response(self.api)
                    ports = self.deserialize(self.fmt, res)
                    port = ports['ports'][0]
                    self.assertIsNotNone(port[ext_qos.QOS])
                    self._delete('ports', port['id'])

    def test_get_qos(self):
        with self.qos(self.default_qos) as qos:
            res = self.new_show_request('qoses', qos['qos']['id'])
            qos_resp = self.deserialize(self.fmt,
                                        res.get_response(self.ext_api))
            self.assertEqual(qos_resp['qos']['policies'],
                             self.default_qos['policies'])

    def test_invalid_policy(self):
        resp = self._create_qos(self.invalid_policy['type'],
                                self.invalid_policy['description'],
                                self.invalid_policy['policies'])
        self.assertIn(ext_qos.QoSValidationError.message, resp.body)

    def test_invalid_update_qos(self):
        with self.qos(self.default_qos) as qos:
            data = {'qos': self.invalid_policy}
            res = self.new_update_request('qoses', data, qos['qos']['id'])
            resp = self.deserialize(self.fmt,
                                    res.get_response(self.ext_api))
            self.assertEqual(ext_qos.QoSValidationError.message,
                             resp['NeutronError']['message'])

    def test_update_mapping_for_network(self):
        with self.network() as n:
            with self.qos(self.default_qos) as qos:
                data = {'network': {ext_qos.QOS: qos['qos']['id']}}
                req = self.new_update_request('networks', data,
                                              n['network']['id'])
                res = self.deserialize(self.fmt, req.get_response(self.api))
                self.assertEqual(res['network'][ext_qos.QOS], qos['qos']['id'])

                with self.qos(self.update_qos) as new_qos:
                    data['network'][ext_qos.QOS] = new_qos['qos']['id']
                    req = self.new_update_request('networks',
                                                  data,
                                                  n['network']['id'])
                    res = self.deserialize(self.fmt,
                                           req.get_response(self.api))
                    self.assertNotEqual(res['network'][ext_qos.QOS],
                                        qos['qos']['id'])
                    self.assertEqual(res['network'][ext_qos.QOS],
                                     new_qos['qos']['id'])

    def test_update_mapping_for_port(self):
        with self.network() as n:
            with self.subnet(n):
                with self.qos(self.default_qos) as qos:
                    res = self._create_port(self.fmt, n['network']['id'])
                    port = self.deserialize(self.fmt, res)
                    data = {'port': {'fixed_ips': port['port']['fixed_ips'],
                                     'name': port['port']['name'],
                                     ext_qos.QOS: qos['qos']['id']}}
                    req = self.new_update_request('ports', data,
                                                  port['port']['id'])
                    res = self.deserialize(self.fmt,
                                           req.get_response(self.api))

                    with self.qos(self.update_qos) as new_qos:
                        data['port'][ext_qos.QOS] = new_qos['qos']['id']
                        req = self.new_update_request('ports', data,
                                                      port['port']['id'])
                        res = self.deserialize(self.fmt, req.get_response(
                                               self.api))
                        self.assertNotEqual(res['port'][ext_qos.QOS],
                                            qos['qos']['id'])
                        self.assertEqual(res['port'][ext_qos.QOS],
                                         new_qos['qos']['id'])
                self._delete('ports', res['port']['id'])

    def test_update_qos(self):
        with self.qos(self.default_qos) as qos:
            data = {'qos': self.update_qos}
            res = self.new_update_request('qoses', data, qos['qos']['id'])
            qos_resp = self.deserialize(self.fmt,
                                        res.get_response(self.ext_api))
            self.assertNotEqual(qos_resp['qos']['policies'],
                                self.default_qos['policies'])
            self.assertEqual(qos_resp['qos']['policies'],
                             self.update_qos['policies'])
