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

from neutron.tests.unit import test_extension_qos as test_qos

PLUGIN_NAME = ('neutron.plugins.ml2.'
               'plugin.Ml2Plugin')
AGENT_NAME = ('neutron.plugins.openvswitch.'
              'agent.ovs_neutron_agent.OVSNeutronAgent')
NOTIFIER = ('neutron.plugins.ml2.'
            'rpc.AgentNotifierApi')


class Ml2QoSTestCase(test_qos.QoSDBTestCase):
    _plugin_name = PLUGIN_NAME

    def setUp(self, plugin=None):
        self.addCleanup(mock.patch.stopall)
        notifier_p = mock.patch(NOTIFIER)
        notifier_cls = notifier_p.start()
        self.notifier = mock.Mock()
        notifier_cls.return_value = self.notifier
        super(Ml2QoSTestCase, self).setUp(PLUGIN_NAME)

    def tearDown(self):
        super(Ml2QoSTestCase, self).tearDown()


class TestMl2QoS(Ml2QoSTestCase,
                 test_qos.TestQoS):
    pass
