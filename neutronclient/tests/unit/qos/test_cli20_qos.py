# Copyright 2012 OpenStack Foundation.
# All Rights Reserved
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

import sys

import mox

from neutronclient.neutron.v2_0.qos import qos
from neutronclient.tests.unit import test_cli20


class CLITestV20QoSJson(test_cli20.CLITestV20Base):

    def setUp(self):
        super(CLITestV20QoSJson, self).setUp(plurals={'qoses': 'qos'})

    def test_create_qos_with_params(self):
        def setup_create_stub(resources, data):
            reses = {resources: data}
            resstr = self.client.serialize(reses)
            resp = (test_cli20.MyResp(200), resstr)
            path = getattr(self.client, resources + '_path')
            self.client.httpclient.request(
                test_cli20.end_url(path), 'POST',
                body=resstr,
                headers=mox.ContainsKeyValue('X-Auth-Token',
                                             test_cli20.TOKEN)).AndReturn(resp)
        qos_type = 'dscp'
        description = 'test QoS'
        tenant_id = 'my-tenant'
        policies = "dscp=20"
        expected = [('description', 'policies', 'tenant_id', 'type'),
                    (description, '{"dscp": "20"}', tenant_id, qos_type)]
        args = ['--type', qos_type,
                '--description', description,
                '--tenant-id', tenant_id,
                '--policies', policies
                ]
        resource = 'qos'
        cmd = qos.CreateQoS(test_cli20.MyApp(sys.stdout), None)
        qos_data = {"tenant_id": tenant_id,
                    "type": qos_type,
                    "description": description,
                    "policies": {"dscp": "20"}
                    }

        self.mox.StubOutWithMock(cmd, 'get_client')
        self.mox.StubOutWithMock(self.client.httpclient, 'request')
        cmd.get_client().AndReturn(self.client)
        setup_create_stub(resource, qos_data)
        self.mox.ReplayAll()

        cmd_parser = cmd.get_parser('create_qos')
        parsed_args = cmd_parser.parse_args(args)
        result = cmd.get_data(parsed_args)

        for res, exp in zip(result, expected):
            self.assertEqual(res, exp)

        self.mox.VerifyAll()
