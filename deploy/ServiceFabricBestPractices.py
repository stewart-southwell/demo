__author__ = "Alexander Johnson"
__email__ = "aljo-microsoft@github.com"
__status__ = "Development"

from datetime import datetime
import xml.etree.ElementTree
import json
from pathlib import Path
from subprocess import PIPE
from subprocess import Popen
import sys
import zipfile

class Resource_Declaration:
    # Microservice development Best Practice in Azure, is Service Fabric Applications, that are managed by
    # Azure Resource Manager.
    #
    # A vital component of success in delivering your SLA/O's will require you to make decisions.
    # E.G. may include using a x509 certificates issued by a trusted Certificate Authority.
    #
    # This was tested October 5 2018 using Azure Cloud Shell.
    #
    # Declared Arguments overwrite template values.
    def __init__(
        self,
        subscription='eec8e14e-b47d-40d9-8bd9-23ff5c381b40',
        ):

        # Owner
        self.subscription = subscription

	# Minimum Service Fabric Cluster Values
        self.template_file = 'AzureDeploy.json'
        self.parameters_file = 'AzureDeploy.Parameters.json'
        self.deployment_resource_group = 'demobpdeployrg'
        self.keyvault_resource_group = 'demobpkeyvaultrg'
        self.keyvault_name = 'demobpkeyvault'
        self.cluster_name = 'demobpcluster'
        self.admin_user_name = 'demo'
        self.admin_password = 'Password#1234'
        self.location = 'westus'
        self.certificate_name = 'x509certificatename'
        self.certificate_thumbprint = 'GEN-CUSTOM-DOMAIN-SSLCERT-THUMBPRINT'
        self.source_vault_value = 'GEN-KEYVAULT-RESOURCE-ID'
        self.certificate_url_value = 'GEN-KEYVAULT-SSL-SECRET-URI'
        self.user_email = 'aljo-microsoft@github.com'

        # Default Values for Program
        self.dns_name = self.cluster_name + "." + self.location + ".cloudapp.azure.com"
        self.certificate_file_name = self.certificate_name + ".pem"
        self.parameters_file_arg = "@" + self.parameters_file

        # Default Values for Microservices App 
        self.microservice_app_package_name = 'MicroserviceApp.sfpkg'
        self.storage_account_name = 'demobpstorage'
        self.container_name = 'demobpscontainer'

	# Default Valyes for GoService
	self.go_service_source_path = '../build/goservice'
        self.go_service_image_tag = "goservice:1.0"
        self.go_service_mongo_db_account_name = "goserviceuser"
        self.go_service_mongo_db_name = "goservicemongodb"
        self.go_service_acr_name = "goserviceacr"
	self.acr_username = self.go_service_mongo_db_name
        self.acr_password = 'GEN-UNIQUE-PASSWORD'
        self.acregistry = self.go_service_acr_name + ".azurecr.io"
        self.acregistry_image_tag = self.acregistry + "/" + self.go_service_image_tag
	
        # Default values for JavaService
        self.java_service_source_path = '../build/javaservice'
	self.java_service_name = 'JavaService'

        # Az CLI Client
        account_set_process = Popen(["az", "account", "set", "--subscription", self.subscription])

        if account_set_process.wait() != 0:
            sys.exit()
        
        print("Deployment Subscription Valid")
        
        # Get Parameter Values
        if Path(self.parameters_file).exists():
            parameters_file_json = json.load(open(self.parameters_file, 'r'))
        else:
            sys.exit("Parameters Not Found")

        # Secrets are passed in as arguments, or fetched from Managed Service
        if self.source_vault_value.find('/subscriptions/') >= 0 and len(self.certificate_thumbprint) > 36 and self.certificate_url_value.find('vault.azure.net') > -1:
            print('Validating Secret Arguments')
        # Demo only - allow redeployment using declared secret values
        elif parameters_file_json['parameters']['sourceVaultValue']['value'].find('/subscriptions/') >= 0 and len(parameters_file_json['parameters']['certificateThumbprint']['value']) > 36 and parameters_file_json['parameters']['certificateUrlValue']['value'].find('vault.azure.net') > -1:
            print('Validating Secret in Parameters File')
            self.source_vault_value = parameters_file_json['parameters']['sourceVaultValue']['value']
            self.certificate_thumbprint = parameters_file_json['parameters']['certificateThumbprint']['value']
            self.certificate_url_value = parameters_file_json['parameters']['certificateUrlValue']['value']
        else:
            # Get Secrets from KeyVault
            print('Making Keyvault Certificate')
            keyvault_group_create_process = Popen(["az", "group", "create", "--name", self.keyvault_resource_group, "--location", self.location])

            if keyvault_group_create_process.wait() != 0:
                sys.exit()

            keyvault_create_process = Popen(["az", "keyvault", "create", "--name", self.keyvault_name, "--resource-group", self.keyvault_resource_group, "--enabled-for-deployment", "true"])

            if keyvault_create_process.wait() != 0:
                sys.exit()

            # Keyvault DNS Population Takes 10 Secs
            keyvault_show_process = Popen(["az", "keyvault", "show", "-n", self.keyvault_name, "-g", self.keyvault_resource_group])

            if keyvault_show_process.wait() != 0:
                sys.exit()

            # Create Self Signed Certificate
            # Get Default Policy
            default_policy_process = Popen(["az", "keyvault", "certificate", "get-default-policy"], stdout=PIPE, stderr=PIPE)

            stdout, stderr = default_policy_process.communicate()

            if default_policy_process.wait() == 0:
                default_policy_json = json.loads(stdout.decode("utf-8"))
            else:
                sys.exit(stderr)

            # Set Subject Name to FQDN
            # Browsers won't trust certificates with subject names that don't match FQDN
            default_policy_json['x509CertificateProperties']['subject'] = "CN=" + self.dns_name
            default_policy_json['x509CertificateProperties']['sans'] = {'dns_names': [self.dns_name], 'emails': [self.user_email], 'upns': [self.user_email]} 
            policy_file_name = "policy.json"
            policy_file_arg = "@" + policy_file_name
            json.dump(default_policy_json, open(policy_file_name, 'w+'))

            certificate_create_process = Popen(["az", "keyvault", "certificate", "create", "--vault-name", self.keyvault_name, "-n", self.certificate_name, "-p", policy_file_arg], stdout=PIPE, stderr=PIPE)

            if certificate_create_process.wait() != 0:
                sys.exit()

            # Get Keyvault Self Signed Certificate Properties
            # Get resource Id
            resource_id_process = Popen(["az", "keyvault", "show", "--name", self.keyvault_name, "--query", "id", "-o", "tsv"], stdout=PIPE, stderr=PIPE)

            stdout, stderr = resource_id_process.communicate()

            if resource_id_process.wait() == 0:
                self.source_vault_value = stdout.decode("utf-8").replace('\n', '')
            else:
                sys.exit(stderr)

            # Get Certificate Url
            url_process = Popen(["az", "keyvault", "certificate", "show", "--vault-name", self.keyvault_name, "--name", self.certificate_name, "--query", "sid", "-o", "tsv"], stdout=PIPE, stderr=PIPE)

            stdout, stderr = url_process.communicate()

            if url_process.wait() == 0:
                self.certificate_url_value = stdout.decode("utf-8").replace('\n', '')
            else:
                sys.exit(stderr)

            # Get Certificate Thumbprint
            thumbprint_process = Popen(["az", "keyvault", "certificate", "show", "--vault-name", self.keyvault_name, "--name", self.certificate_name, "--query", "x509ThumbprintHex", "-o", "tsv"], stdout=PIPE, stderr=PIPE)

            stdout, stderr = thumbprint_process.communicate()

            if thumbprint_process.wait() == 0:
                self.certificate_thumbprint = stdout.decode("utf-8").replace('\n', '')
            else:
                sys.exit(stderr)

        # Validate KeyVault Resource Availability
        validate_source_vault = Popen(["az", "resource", "show", "--ids", self.source_vault_value])

        if validate_source_vault.wait() != 0:
            sys.exit()

        # Certificate URL
        self.keyvault_name = self.certificate_url_value.rsplit("//", 1)[1].rsplit(".vault.", 1)[0]
        self.certificate_name = self.certificate_url_value.rsplit("//", 1)[1].rsplit(".vault.", 1)[1].rsplit("/", 3)[2]

        cert_url_validate_process = Popen(["az", "keyvault", "certificate", "show", "--vault-name", self.keyvault_name, "--name", self.certificate_name, "--query", "sid", "-o", "tsv"])

        if cert_url_validate_process.wait() != 0:
            sys.exit()

        # Certificate Thumbprint
        cert_thumbprint_validate_process = Popen(["az", "keyvault", "certificate", "show", "--vault-name", self.keyvault_name, "--name", self.certificate_name, "--query", "x509ThumbprintHex", "-o", "tsv"])

        if cert_thumbprint_validate_process.wait() != 0:
            sys.exit()

        # Declare Certificate
        parameters_file_json['parameters']['sourceVaultValue']['value'] = self.source_vault_value
        parameters_file_json['parameters']['certificateThumbprint']['value'] = self.certificate_thumbprint
        parameters_file_json['parameters']['certificateUrlValue']['value'] = self.certificate_url_value

        # Prefer Arguments
        parameters_file_json['parameters']['clusterName']['value'] = self.cluster_name
        parameters_file_json['parameters']['adminUserName']['value'] = self.admin_user_name
        parameters_file_json['parameters']['adminPassword']['value'] = self.admin_password
        parameters_file_json['parameters']['location']['value'] = self.location

        # Write Template
        json.dump(parameters_file_json, open(self.parameters_file, 'w'))

        # Exists or Create Deployment Group - needed for validation
        deployment_group_exists_process = Popen(["az", "group", "exists", "--name", self.deployment_resource_group], stdout=PIPE, stderr=PIPE)

        stdout, stderr = deployment_group_exists_process.communicate()

        if stdout.decode('utf-8').replace('\n', '') != 'true':
            deployment_group_create_process = Popen(["az", "group", "create", "--location", self.location, "--name", self.deployment_resource_group], stdout=PIPE, stderr=PIPE)

            if deployment_group_create_process.wait() != 0:
                sys.exit(stderr)

        # Resource Declaration
        if not Path(self.template_file).exists():
            sys.exit("Template File Not Found")

    def validate_declaration(self):
        # Validate Deployment Declaration
        deployment_validation_process = Popen(["az", "group", "deployment", "validate", "--resource-group", self.deployment_resource_group, "--template-file", self.template_file, "--parameters", self.parameters_file_arg], stdout=PIPE, stderr=PIPE)

        stdout, stderr = deployment_validation_process.communicate()

        if deployment_validation_process.wait() == 0:
            print("Your Deployment Declaration is Valid Syntactically")
        else:
            print(stdout)
            sys.exit(stderr)

    def deploy_resources(self):
        # Reduce LiveSite issues by deploying Azure Resources in a Declarative way as a group
        deployment_name = "bestpracticedeployment"

        print("Deploying Resources")
        group_deployment_create_process = Popen(["az", "group", "deployment", "create", "-g", self.deployment_resource_group, "--name", deployment_name, "--template-file", self.template_file, "--parameters", self.parameters_file_arg], stdout=PIPE, stderr=PIPE)

        stdout, stderr = group_deployment_create_process.communicate()

        if group_deployment_create_process.wait() != 0:
            print(stdout)
            print(stderr)
	
        print("Resource Deployment Successful")

    def setup_cluster_client(self):
        # Downloads client admin certificate
        # Convert to PEM format for linux compatibility
        print("Downloading Certificate")
        certificate_b64_file = self.certificate_name + "64.pem"
        download_cert_process = Popen(["az", "keyvault", "secret", "download", "--file", certificate_b64_file, "--encoding", "base64", "--name", self.certificate_name, "--vault-name", self.keyvault_name], stdout=PIPE, stderr=PIPE)

        stdout, stderr = download_cert_process.communicate()

        if download_cert_process.wait() != 0:
            print(stdout)
            print(stderr)

        convert_cert_process = Popen(["openssl", "pkcs12", "-in", certificate_b64_file, "-out", self.certificate_file_name, "-nodes", "-passin", "pass:"], stdout=PIPE, stderr=PIPE)

        stdout, stderr = convert_cert_process.communicate()

        if convert_cert_process.wait() != 0:
            print(stdout)
            print(stderr)

    def cluster_connection(self):
        endpoint = 'https://' + self.dns_name + ':19080'

        cluster_connect_process = Popen(["sfctl", "cluster", "select", "--endpoint", endpoint, "--pem", self.certificate_file_name, "--no-verify"])

        if not cluster_connect_process.wait() == 0:
            sys.exit("Unable to Connect to Cluster")

    def go_service_build(self):
        # Build GoService Container Image
        go_service_build_process = Popen(["docker", "build", "../build/goservice/", "--tag", self.go_service_image_tag])
	
	if not go_service_build_process.wait() == 0:
            sys.exit("couldn't build GoService Docker Image")
        # Create ACR go GoService
        acr_create_process = Popen(["az", "acr", "create", "--name", self.go_service_acr_name, "--resource-group", self.deployment_resource_group, "--sku", "Basic", "--admin-enabled", "true"])

        if not acr_create_process.wait() == 0:
            sys.exit("Couldn't create ACR")
        # Get ACR User Name
        acr_username_process = Popen(["az", "acr", "credential", "show", "-n", self.go_service_acr_name, "--query", "username"], stdout=PIPE, stderr=PIPE)

        stdout, stderr = acr_username_process.communicate()

        if acr_username_process.wait() == 0:
            self.acr_username = stdout.decode("utf-8").replace('\n', '')
        else:
            sys.exit(stderr)
        # Get ACR Password
        acr_password_process = Popen(["az", "acr", "credential", "show", "-n", self.go_service_acr_name, "--query", "passwords[0].value"], stdout=PIPE, stderr=PIPE)

        stdout, stderr = acr_password_process.communicate()

        if acr_password_process.wait() == 0:
            self.acr_password = stdout.decode("utf-8").replace('\n', '')
        else:
            sys.exit(stderr)
        # Login to ACR
        acr_login_process = Popen(["docker", "login", self.acregistry, "-u", self.acr_username, "-p", self.acr_password])

        if not acr_login_process.wait() == 0:
            sys.exit("Couldn't login into ACR")

        # Push Image to ACR
        push_image_process = Popen(["docker", "push", self.acregistry_image_tag])

        if not push_image_process.wait() == 0:
            sys.exit("Couldn't push Image")

    def go_service_cosmos_db_creation(self):
        # Craete Cosmos DB Account
        cosmos_account_create_process = Popen(["az", "cosmosdb", "create", "--name", self.go_service_mongo_db_account_name, "--resource-group", self.deployment_resource_group, "--kind", "MongoDB"])

        if not cosmos_account_create_process.wait() == 0:
            sys.exit("couldn't create GoApp Cosmos DB User")

        cosmos_database_create_process = Popen(["az", "cosmosdb", "database", "create", "--db-name", self.go_service_mongo_db_name, "--name", self.go_service_mongo_db_account_name, "--resource-group", self.deployment_resource_group])

        if not cosmos_database_create_process.wait() == 0:
            sys.exit("Couldn't crate Go App Cosmos Mongo DB")

    def go_service_sfpkg_declaration(self):
        # Get ACR URL
        # Get Cosmos DB Password
        # Update SF Package with: acr_username, acr_password, go_app_mongo_db_account_name, go_app_mongo_db_password
        # Get Package Properties for RM Template

    def classic_java_service_build(self):
        # javac ./javapp/JavaApp.java
        self.java_service_source_path = '../build/javaservice'
	self.java_service_name = 'JavaService'

    def classic_java_service_sfpkg_declaration(self):
        # copy ./javaapp/JavaApp.class to ./javapp/javacode/
        # Update SF Packge with: Service Version, JavaApp.class 
        # Get Package Properties for RM Template
        classic_app_name = 'JavaApp'
        classic_app_package = 'JavaApp.sfpkg'

    def microservices_app_sfpkg(self):
        # 
	# Create solution_v1.0.sfpkg
        # Create Storage Account
        # Get Connection String to Storage Account
        # Create Storage Account Blob Container
        # Upload SF Packge to Account blob
        # Get Public url to file in storage account blob
        print("Packing Microservices Solution")

        # Use Public URL instead of creating one
        # Create Storate
        create_storage_process = Popen(["az", "storage", "account", "create", "-n", self.storage_account_name, "-g", self.deployment_resource_group, "-l", self.location, "--sku", "Standard_LRS"], stdout=PIPE, stderr=PIPE)

        stdout, stderr = create_storage_process.communicate()

        if create_storage_process.wait() == 0:
            print("Storage Account Created")
        else:
            sys.exit(stderr)

        # Get Connection String
        connection_string_process = Popen(["az", "storage", "account", "show-connection-string", "-g", self.deployment_resource_group, "-n", self.storage_account_name], stdout=PIPE, stderr=PIPE)

        stdout, stderr = connection_string_process.communicate()

        if connection_string_process.wait() == 0:
            connection_string = str(json.loads(stdout.decode("utf-8"))['connectionString'])
            print("Got Storage Connection String")
        else:
            sys.exit(stderr)

        # Create Blob Container
        create_container_process = Popen(["az", "storage", "container", "create", "--name", self.container_name, "--connection-string", connection_string, "--public-access", "container"], stdout=PIPE, stderr=PIPE)

        stdout, stderr = create_container_process.communicate()

        if create_container_process.wait() == 0:
            print("Blob Container Created")
        else:
            sys.exit(stderr)

        # Upload SFPKG to Blob Container
        upload_classic_process = Popen(["az", "storage", "blob", "upload", "--file", self.classic_app_package, "--name", classic_app_name, "--connection-string", connection_string, "--container-name", self.container_name], stdout=PIPE, stderr=PIPE)

        stdout, stderr = upload_poa_process.communicate()

        if upload_poa_process.wait() == 0:
            print("Uploaded Classic PKG To Storage Account Blob Container")
        else:
            sys.exit(stderr)

        # Get URL for Solution in Storage Account Blob Container
        url_blob_process = Popen(["az", "storage", "blob", "url", "--container-name", self.container_name, "--connection-string", connection_string, "--name", classic_app_name], stdout=PIPE, stderr=PIPE)

        stdout, stderr = url_blob_process.communicate()

        if url_blob_process.wait() == 0:
            classic_app_package_url = stdout.decode("utf-8").replace('\n', '').replace('"', '')
            print("Got URL for Classic file in Storage Account Blob")
        else:
            sys.exit(stderr)

    def microservices_app_resource_declaration(self):
        # Update Template with Application, App Type, App Version, Service Type's (go app, and classic java)

        print("Updating Resource Declaration Microservices SolutionJavaApp")

        # TODO: Below needs to be updated to only append Service to Application type
        #       Will delcare Type with GoApp.
	# Declare Classic App Services as resources that is apart of microservices Application
        # Unzip SFPKG and Get Properties
        print("Declaring classic app in template")
        template_file_json = json.load(open(self.template_file, 'r'))
        classic_app_sfpkg = zipfile.ZipFile(self.classic_app_name, "r")
        classic_app_sfpkg.extractall(classic_app_name)
        application_manifest_path = classic_app_name + "/ApplicationManifest.xml"
        application_manifest = xml.etree.ElementTree.parse(application_manifest_path).getroot()
        sfpkg_application_type_version = application_manifest.attrib['ApplicationTypeVersion']
        sfpkg_application_type_name = application_manifest.attrib['ApplicationTypeName']

        for i in range(len(application_manifest)):
            if application_manifest[i].tag == '{http://schemas.microsoft.com/2011/01/fabric}DefaultServices':
                poa_services = application_manifest[i].getchildren()
                for j in range(len(poa_services)):
                    if poa_services[j].attrib['Name'].lower().find("coordinator") > -1:
                        sfpkg_coordinator_service_name = poa_services[j].attrib['Name']
                        sfpkg_coordinator_service_type = poa_services[j].getchildren()[0].attrib['ServiceTypeName']
                    elif poa_services[j].attrib['Name'].lower().find("nodeagent") > -1:
                        sfpkg_node_agent_service_name = poa_services[j].attrib['Name']
                        sfpkg_node_agent_service_type = poa_services[j].getchildren()[0].attrib['ServiceTypeName']
                    else:
                        sys.exit("couldn't find coordinator or nodeagent services properties in Application Manifest")

        # ApplicationType
        application_type_depends_on = "[concat('Microsoft.ServiceFabric/clusters/', parameters('clusterName'))]"
        application_type_name = "[concat(parameters('clusterName'), '/', '" + sfpkg_application_type_name + "')]"
        template_file_json["resources"] += [
            {
                "apiVersion": "2017-07-01-preview",
                "type": "Microsoft.ServiceFabric/clusters/applicationTypes",
                "name": application_type_name,
                "location": "[variables('location')]",
                "dependsOn": [
                    application_type_depends_on
                ],
                "properties": {
                    "provisioningState": "Default"
                }
            }
        ]
        # ApplicationTypeVersion
        application_type_version = "[concat(parameters('clusterName'), '/', '" + sfpkg_application_type_name + "', '/', '" + sfpkg_application_type_version + "')]"
        application_type_version_depends_on = "[concat('Microsoft.ServiceFabric/clusters/', parameters('clusterName'), '/applicationTypes/', '" + sfpkg_application_type_name + "')]"
        template_file_json["resources"] += [
            {
                "apiVersion": "2017-07-01-preview",
                "type": "Microsoft.ServiceFabric/clusters/applicationTypes/versions",
                "name": application_type_version,
                "location": "[variables('location')]",
                "dependsOn": [
                    application_type_version_depends_on
                ],
                "properties": {
                    "provisioningState": "Default",
                    "appPackageUrl": poa_package_url
                }
            }
        ]

        # Application
        application_name = "[concat(parameters('clusterName'), '/', '" + poa_name + "')]"
        application_name_dependends_on = "[concat('Microsoft.ServiceFabric/clusters/', parameters('clusterName'), '/applicationTypes/', '" + sfpkg_application_type_name + "', '/versions/', '" + sfpkg_application_type_version + "')]"
        template_file_json["resources"] += [
            {
                "apiVersion": "2017-07-01-preview",
                "type": "Microsoft.ServiceFabric/clusters/applications",
                "name": application_name,
                "location": "[variables('location')]",
                "dependsOn": [
                    application_name_dependends_on
                ],
                "properties": {
                    "provisioningState": "Default",
                    "typeName": sfpkg_application_type_name,
                    "typeVersion": sfpkg_application_type_version,
                    "parameters": {},
                    "upgradePolicy": {
                        "upgradeReplicaSetCheckTimeout": "01:00:00.0",
                        "forceRestart": "false",
                        "rollingUpgradeMonitoringPolicy": {
                            "healthCheckWaitDuration": "00:02:00.0",
                            "healthCheckStableDuration": "00:05:00.0",
                            "healthCheckRetryTimeout": "00:10:00.0",
                            "upgradeTimeout": "01:00:00.0",
                            "upgradeDomainTimeout": "00:20:00.0"
                        },
                        "applicationHealthPolicy": {
                            "considerWarningAsError": "false",
                            "maxPercentUnhealthyDeployedApplications": "50",
                            "defaultServiceTypeHealthPolicy": {
                                "maxPercentUnhealthyServices": "50",
                                "maxPercentUnhealthyPartitionsPerService": "50",
                                "maxPercentUnhealthyReplicasPerPartition": "50"
                            }
                        }
                    }
                }
            }
        ]

        # NodeAgent Service
        node_agent_service_name = "[concat(parameters('clusterName'), '/', '" + poa_name + "', '/', '" + poa_name + "~" + sfpkg_node_agent_service_name + "')]"
        node_agent_service_depends_on = "[concat('Microsoft.ServiceFabric/clusters/', parameters('clusterName'), '/applications/', '" + poa_name + "')]"
        template_file_json["resources"] += [
            {
                "apiVersion": "2017-07-01-preview",
                "type": "Microsoft.ServiceFabric/clusters/applications/services",
                "name": node_agent_service_name,
                "location": "[variables('location')]",
                "dependsOn": [
                    node_agent_service_depends_on
                ],
                "properties": {
                    "provisioningState": "Default",
                    "serviceKind": "Stateless",
                    "serviceTypeName": sfpkg_node_agent_service_type,
                    "instanceCount": "-1",
                    "partitionDescription": {
                        "partitionScheme": "Singleton"
                    },
                    "correlationScheme": [],
                    "serviceLoadMetrics": [],
                    "servicePlacementPolicies": []
                }
            }
        ]
        # Coordinator Service
        coordinator_service_name = "[concat(parameters('clusterName'), '/', '" + poa_name + "', '/', '" + poa_name + "~" + sfpkg_coordinator_service_name + "')]"
        coordinator_service_depends_on = "[concat('Microsoft.ServiceFabric/clusters/', parameters('clusterName'), '/applications/', '" + poa_name + "')]"
        template_file_json["resources"] += [
            {
                "apiVersion": "2017-07-01-preview",
                "type": "Microsoft.ServiceFabric/clusters/applications/services",
                "name": coordinator_service_name,
                "location": "[variables('location')]",
                "dependsOn": [
                    coordinator_service_depends_on
                ],
                "properties": {
                    "provisioningState": "Default",
                    "serviceKind": "Stateful",
                    "serviceTypeName": sfpkg_coordinator_service_type,
                    "targetReplicaSetSize": "3",
                    "minReplicaSetSize": "2",
                    "replicaRestartWaitDuration": "00:01:00.0",
                    "quorumLossWaitDuration": "00:02:00.0",
                    "standByReplicaKeepDuration": "00:00:30.0",
                    "partitionDescription": {
                        "partitionScheme": "UniformInt64Range",
                        "count": "5",
                        "lowKey": "1",
                        "highKey": "5"
                    },
                    "hasPersistedState": "true",
                    "correlationScheme": [],
                    "serviceLoadMetrics": [],
                    "servicePlacementPolicies": [],
                    "defaultMoveCost": "Low"
                }
            }
        ]

        # Update Template File
        template_file = open(self.template_file, 'w')
        json.dump(template_file_json, template_file)
        template_file.close()

    def Enable_Host_MSI(self):
        # Update template to enable host MSi and apply policies
        print("TODO: Enable Host MSI")

    def Set_MSI_Permissions(self):
        # grant AAD permissions to MSI for resource such as Cosmos DB
        print("TODO: Apply Permissions to Resource for MSI")

def main():
    demo_start = datetime.now()

    resource_declaration = Resource_Declaration()

    resource_declaration.go_service_build()
    resource_declaration.classic_java_service_build()
    resource_declaration.go_service_sfpkg_declaration()
    resource_declaration.classic_java_service_sfpkg_declaration()
    resource_declaration.microservices_app_sfpkg()
    resource_declaration.microservices_app_resource_declaration()

    resource_declaration.validate_declaration()

    resource_declaration.deploy_resources()
    print("Deployed Modern Microservices solution on SF Cluster Duration: " + str(datetime.now() - demo_start))

    resource_declaration.setup_cluster_client()
    #resourceDeclaration.Enable_Host_MSI()
    #resourceDeclaration.Set_MSI_Permissions()

if __name__ == '__main__':
    main()
