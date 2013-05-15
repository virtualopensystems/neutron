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
import mock

from neutron.agent import rpc as agent_rpc
from neutron.db import qos_rpc_base as qos_db_rpc
from neutron.openstack.common.rpc import proxy
from neutron.services.qos.agents import qos_rpc as qos_agent_rpc
from neutron.tests import base
from neutron.tests.unit import test_extension_qos as test_qos


QOS_BASE_PACKAGE = 'neutron.services.qos.drivers'
OPENFLOW_DRIVER = QOS_BASE_PACKAGE + '.openflow.OpenflowQoSVlanDriver'


class FakeQoSCallback(qos_db_rpc.QoSServerRpcCallbackMixin):
    pass


class QoSServerRpcCallbackMixinTestCase(test_qos.QoSDBTestCase):
    def setUp(self):
        super(QoSServerRpcCallbackMixinTestCase, self).setUp()
        self.rpc = FakeQoSCallback()


class FakeQoSRpcApi(agent_rpc.PluginApi,
                    qos_agent_rpc.QoSServerRpcApiMixin):
    pass


class QoSServerRpcApiTestCase(base.BaseTestCase):
    def setUp(self):
        super(QoSServerRpcApiTestCase, self).setUp()
        self.rpc = FakeQoSRpcApi('fake_topic')
        self.rpc.call = mock.Mock()

    def test_get_policy_for_qos(self):
        self.rpc.get_policy_for_qos(None, 'fake-qos')
        self.rpc.call.assert_has_calls(
            [mock.call(None,
                       {'args': {'qos_id': 'fake-qos'},
                        'method': 'get_policy_for_qos',
                        'namespace': None},
                       version=qos_agent_rpc.QOS_RPC_VERSION,
                       topic='fake_topic')])

    def test_get_qos_by_network(self):
        self.rpc.get_qos_by_network(None, 'fake-network')
        self.rpc.call.assert_has_calls(
            [mock.call(None,
                       {'args': {'network_id': 'fake-network'},
                        'method': 'get_qos_by_network',
                        'namespace': None},
                       version=qos_agent_rpc.QOS_RPC_VERSION,
                       topic='fake_topic')])


class QoSAgentRpcTestCase(base.BaseTestCase):
    def setUp(self):
        super(QoSAgentRpcTestCase, self).setUp()
        self.agent = qos_agent_rpc.QoSAgentRpcMixin()
        self.agent.context = None
        self.fake_policy = {"fake": "qos"}
        rpc = mock.Mock()
        rpc.get_policy_for_qos.return_value = self.fake_policy
        self.agent.plugin_rpc = rpc
        self.agent.qos = mock.Mock()

    def test_network_qos_deleted(self):
        self.agent.network_qos_deleted(None, 'fake-qos', 'fake-network')
        self.agent.qos.delete_qos_for_network.assert_has_calls(
            [mock.call('fake-network')])

    def test_network_qos_updated(self):
        self.agent.network_qos_updated(None, 'fake-qos', 'fake-network')
        self.agent.plugin_rpc.get_policy_for_qos.assert_has_calls(
            [mock.call(None, 'fake-qos')])
        self.agent.qos.network_qos_updated.assert_has_calls(
            [mock.call(self.fake_policy, 'fake-network')])

    def test_port_qos_updated(self):
        self.agent.port_qos_updated(None, 'fake-qos', 'fake-port')
        self.agent.qos.port_qos_updated.assert_has_calls(
            [mock.call(self.fake_policy, 'fake-port')])

    def test_port_qos_deleted(self):
        self.agent.port_qos_deleted(None, 'fake-qos', 'fake-port')
        self.agent.qos.delete_qos_for_port.assert_has_calls(
            [mock.call('fake-port')])


class FakeQoSNotifierApi(proxy.RpcProxy,
                         qos_agent_rpc.QoSAgentRpcApiMixin):
    pass


class QoSAgentRpcApiMixinTestCase(base.BaseTestCase):
    def setUp(self):
        super(QoSAgentRpcApiMixinTestCase, self).setUp()
        self.notifier = FakeQoSNotifierApi(topic='fake_topic',
                                           default_version='1.2')
        self.notifier.fanout_cast = mock.Mock()

    def test_network_qos_updated(self):
        self.notifier.network_qos_updated(None,
                                          network_id='fake-network',
                                          qos_id='fake-qos')
        self.notifier.fanout_cast.assert_has_calls(
            [mock.call(None,
                       {'args':
                        {'network_id': 'fake-network',
                         'qos_id': 'fake-qos'},
                        'method': 'network_qos_updated',
                        'namespace': None},
                       version=qos_agent_rpc.QOS_RPC_VERSION,
                       topic='fake_topic-qos-update')])

    def test_network_qos_deleted(self):
        self.notifier.network_qos_deleted(None,
                                          network_id='fake-network',
                                          qos_id='fake-qos')
        self.notifier.fanout_cast.assert_has_calls(
            [mock.call(None,
                       {'args':
                        {'network_id': 'fake-network',
                         'qos_id': 'fake-qos'},
                        'method': 'network_qos_deleted',
                        'namespace': None},
                       version=qos_agent_rpc.QOS_RPC_VERSION,
                       topic='fake_topic-qos-update')])

    def test_port_qos_deleted(self):
        self.notifier.port_qos_deleted(None,
                                       port_id='fake-port',
                                       qos_id='fake-qos')
        self.notifier.fanout_cast.assert_has_calls(
            [mock.call(None,
                       {'args':
                        {'port_id': 'fake-port',
                         'qos_id': 'fake-qos'},
                        'method': 'port_qos_deleted',
                        'namespace': None},
                       version=qos_agent_rpc.QOS_RPC_VERSION,
                       topic='fake_topic-qos-update')])

    def test_port_qos_updated(self):
        self.notifier.port_qos_updated(None,
                                       port_id='fake-port',
                                       qos_id='fake-qos')
        self.notifier.fanout_cast.assert_has_calls(
            [mock.call(None,
                       {'args':
                        {'port_id': 'fake-port',
                         'qos_id': 'fake-qos'},
                        'method': 'port_qos_updated',
                        'namespace': None},
                       version=qos_agent_rpc.QOS_RPC_VERSION,
                       topic='fake_topic-qos-update')])
