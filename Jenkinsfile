pipeline {
    agent any

    environment {
        VAULT_ADDR = credentials('VAULT_ADDR')
    }

    stages {

        stage('Checkout') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'github-creds',
                    usernameVariable: 'GIT_USER',
                    passwordVariable: 'GIT_TOKEN'
                )]) {
                    git(
                        url: "https://${GIT_USER}:${GIT_TOKEN}@github.com/funmicra/cert-automation.git",
                        branch: 'master'
                    )
                }
            }
        }

        stage('Authenticate to Vault (root – test only)') {
            steps {
                withCredentials([
                    string(credentialsId: 'VAULT_ADDR', variable: 'VAULT_ADDR'),
                    string(credentialsId: 'VAULT_SECRET_ID', variable: 'VAULT_TOKEN')
                ]) {
                    sh '''
                        set -e
                        echo "Authenticating to Vault using root token (test mode)"

                        # Sanity check
                        vault token lookup > /dev/null

                        # Persist token for downstream stages
                        echo "$VAULT_TOKEN" > "${WORKSPACE}/vault.token"

                        echo "Vault root authentication successful"
                    '''
                }
            }
        }


        stage('Issue certificate') {
            steps {
                sh '''
                    set -e
                    export VAULT_TOKEN="$(cat "${WORKSPACE}/vault.token")"
                    echo "Issuing certificate via Vault..."
                    python3 certs_issue.py
                '''
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

                        ssh -i "$SSH_KEY" "$SSH_USER@$REMOTE_HOST" \
                          "mkdir -p $LOCAL_CERT_DIR && chmod 700 $LOCAL_CERT_DIR"

                        scp -i "$SSH_KEY" syndicate.key fullchain.pem \
                          "$SSH_USER@$REMOTE_HOST:$LOCAL_CERT_DIR/"

                        ssh -i "$SSH_KEY" "$SSH_USER@$REMOTE_HOST" \
                          "chmod 600 $LOCAL_CERT_DIR/syndicate.key $LOCAL_CERT_DIR/fullchain.pem"
                    '''
                }
            }
        }

        stage('Validate & reload NGINX') {
            steps {
                sh '''
                    set -e
                    docker exec nginx-reverse-proxy nginx -t
                    docker exec nginx-reverse-proxy nginx -s reload
                '''
            }
        }
    }

    post {
        always {
            sh 'rm -rf "${WORKSPACE}/certs" "${WORKSPACE}/vault.token"'
        }
        failure {
            echo "Certificate rotation failed. NGINX was not reloaded."
        }
    }
}
