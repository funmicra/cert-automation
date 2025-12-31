pipeline {
    agent any

    environment {
        VAULT_ADDR = credentials('VAULT_ADDR')
    }

    stages {
        stage('Authenticate to Vault') {
            steps {
                withCredentials([
                    string(credentialsId: 'VAULT_ADDR', variable: 'VAULT_ADDR'),
                    string(credentialsId: 'VAULT_ROLE_ID', variable: 'ROLE_ID'),
                    string(credentialsId: 'VAULT_SECRET_ID', variable: 'SECRET_ID')
                ]) {
                    sh '''
                        set -e

                        echo "Logging into Vault..."
                        vault write -format=json auth/approle/login \
                            role_id="$ROLE_ID" \
                            secret_id="$SECRET_ID" \
                            | jq -r .auth.client_token > "${WORKSPACE}/vault.token"

                        if [ ! -s "${WORKSPACE}/vault.token" ]; then
                            echo "Vault login failed: token not generated"
                            exit 1
                        fi

                        echo "Vault login successful, token saved to vault.token"
                    '''
                }
            }
        }

        stage('Issue certificate') {
            steps {
                withEnv(["VAULT_TOKEN=$(<${WORKSPACE}/vault.token)"]) {
                    sh '''
                        set -e
                        echo "Issuing certificate via Vault..."
                        python3 certs_issue.py
                    '''
                }
            }
        }


        stage('Copy certs to local NGINX stack') {
            steps {
                withCredentials([
                    sshUserPrivateKey(
                        credentialsId: 'DEBIANSERVER',
                        keyFileVariable: 'SSH_KEY',
                        usernameVariable: 'SSH_USER'
                    )
                ]) {
                    sh '''
                        set -e
                        REMOTE_HOST=192.168.88.22
                        LOCAL_CERT_DIR=/home/funmicra/stacks/nginx-proxy/certs

                        # Ensure directory exists and copy files
                        ssh -i $SSH_KEY $SSH_USER@$REMOTE_HOST "mkdir -p $LOCAL_CERT_DIR && chmod 700 $LOCAL_CERT_DIR"
                        scp -i $SSH_KEY syndicate.key fullchain.pem $SSH_USER@$REMOTE_HOST:$LOCAL_CERT_DIR/
                        ssh -i $SSH_KEY $SSH_USER@$REMOTE_HOST "chmod 600 $LOCAL_CERT_DIR/syndicate.key $LOCAL_CERT_DIR/fullchain.pem"
                    '''
                }
            }
        }

        stage('Validate & reload NGINX') {
            steps {
                sh '''
                    set -e
                    docker exec nginx-reverse-proxy nginx -t && docker exec nginx-reverse-proxy nginx -s reload
                '''
            }
        }
    }

    post {
        always {
            sh 'rm -rf ${WORKSPACE}/certs'
        }
        failure {
            echo "Certificate rotation failed. No reload performed."
        }
    }
}
