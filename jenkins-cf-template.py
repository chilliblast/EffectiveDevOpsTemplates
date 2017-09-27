"""Generating CloudFormation template."""

from ipaddress import ip_network

from ipify import get_ip

from troposphere import (
    Base64,
    ec2,
    GetAtt,
    Join,
    Output,
    Parameter,
    Ref,
    Template,
)

from troposphere.iam import ( 
    InstanceProfile, 
    PolicyType as IAMPolicy, 
    Role,  
) 
 
from awacs.aws import ( 
    Action, 
    Allow, 
    Policy, 
    Principal, 
    Statement, 
) 
 
from awacs.sts import AssumeRole 

ApplicationName = "jenkins"
ApplicationPort = "8080"

GithubAccount = "chilliblast"
GithubAnsibleURL = "https://github.com/{}/ansible".format(GithubAccount)
AnsiblePullCmd = \
	"/usr/local/bin/ansible-pull -U {} {}.yml -i localhost".format(
		GithubAnsibleURL,
		ApplicationName
)
AnsiblePlayBookCmd = \
	"/usr/local/bin/ansible-playbook /tmp/ansible/{}.yml -i localhost".format(
		ApplicationName
)

PublicCidrIp = str(ip_network(get_ip()))

t = Template()

t.add_description("Effective DevOps in AWS: HelloWorld web application")

t.add_resource(Role(
    "Role",
    AssumeRolePolicyDocument=Policy(
        Statement=[
            Statement(
                Effect=Allow,
                Action=[AssumeRole],
                Principal=Principal("Service", ["ec2.amazonaws.com"])
            )
        ]
    )
))

t.add_resource(InstanceProfile( 
    "InstanceProfile", 
    Path="/", 
    Roles=[Ref("Role")] 
)) 

t.add_parameter(Parameter(
    "KeyPair",
    Description="Name of an existing EC2 KeyPair to SSH",
    Type="AWS::EC2::KeyPair::KeyName",
    ConstraintDescription="must be the name of an existing EC2 KeyPair.",
))

t.add_resource(ec2.SecurityGroup(
    "SecurityGroup",
    GroupDescription="Allow SSH and TCP/{} access".format(ApplicationPort),
    SecurityGroupIngress=[
        ec2.SecurityGroupRule(
            IpProtocol="tcp",
            FromPort="22",
            ToPort="22",
            CidrIp=PublicCidrIp,
        ),
        ec2.SecurityGroupRule(
            IpProtocol="tcp",
            FromPort=ApplicationPort,
            ToPort=ApplicationPort,
            CidrIp=PublicCidrIp,
        ),
    ],
))

ud = Base64(Join('\n', [
    "#!/bin/bash",
    "yum install --enablerepo=epel -y git",
    "yum install -y gcc",
    "yum install -y libffi",
    "yum install -y libffi-devel",
    "yum install -y openssl-devel",
    "pip install ansible",
    "cd /tmp;git clone http://github.com/chilliblast/ansible",
#    AnsiblePullCmd,
#    "echo '*/10 * * * * {}' > /etc/cron.d/ansible-pull".format(AnsiblePullCmd),
    AnsiblePlayBookCmd,
    "echo '*/10 * * * * {}' > /etc/cron.d/ansible-playbook".format(AnsiblePlayBookCmd)
]))

t.add_resource(IAMPolicy("Policy", 
    PolicyName="AllowCodePipeline", 
    PolicyDocument=Policy( 
        Statement=[ 
            Statement(Effect=Allow, 
                Action=[Action("codepipeline", "*")], 
                Resource=["*"]) 
        ] 
    ), 
    Roles=[Ref("Role")] 
))

t.add_resource(ec2.Instance(
    "instance",
    ImageId="ami-ebd02392",
    InstanceType="t2.micro",
    SecurityGroups=[Ref("SecurityGroup")],
    KeyName=Ref("KeyPair"),
    UserData=ud,
    IamInstanceProfile=Ref("InstanceProfile"),
))

t.add_output(Output(
    "InstancePublicIp",
    Description="Public IP of our instance.",
    Value=GetAtt("instance", "PublicIp"),
))

t.add_output(Output(
    "WebUrl",
    Description="Application endpoint",
    Value=Join("", [
        "http://", GetAtt("instance", "PublicDnsName"),
        ":", ApplicationPort
    ]),
))

print (t.to_json())
