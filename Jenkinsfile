pipeline {
    agent any

    triggers {
        cron('* * * * *')
    }

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

        stage('Authenticate to Vault (AppRole)') {
            steps {
                withCredentials([
                    string(credentialsId: 'VAULT_ADDR',     variable: 'VAULT_ADDR'),
                    string(credentialsId: 'VAULT_ROLE_ID', variable: 'VAULT_ROLE_ID'),
                    string(credentialsId: 'VAULT_SECRET_ID', variable: 'VAULT_SECRET_ID')
                ]) {
                    sh '''
                        set -e
                        echo "Authenticating to Vault using AppRole"

                        RESPONSE=$(vault write -format=json auth/approle/login \
                            role_id="$VAULT_ROLE_ID" \
                            secret_id="$VAULT_SECRET_ID")

                        VAULT_TOKEN=$(echo "$RESPONSE" | jq -r .auth.client_token)

                        if [ -z "$VAULT_TOKEN" ] || [ "$VAULT_TOKEN" = "null" ]; then
                            echo "Failed to obtain Vault token"
                            exit 1
                        fi

                        echo "$VAULT_TOKEN" > "${WORKSPACE}/vault.token"

                        echo "Vault AppRole authentication successful"
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
                sshagent(['DEBIANSERVER']) {
                    sh '''
                        set -e

                        REMOTE_HOST=192.168.88.22
                        SSH_USER=funmicra
                        LOCAL_CERT_DIR=/etc/nginx/certs
                        CERT_DIR="${WORKSPACE}/certs"

                        SSH_OPTS="-o StrictHostKeyChecking=no -o BatchMode=yes"

                        echo "Verifying certificates exist"
                        test -f "$CERT_DIR/syndicate.key"
                        test -f "$CERT_DIR/fullchain.pem"

                        echo "Preparing certificate directory on remote host"
                        ssh $SSH_OPTS "$SSH_USER@$REMOTE_HOST" \
                        "mkdir -p $LOCAL_CERT_DIR && chmod 700 $LOCAL_CERT_DIR"

                        echo "Copying certificates"
                        scp $SSH_OPTS \
                        "$CERT_DIR/syndicate.key" \
                        "$CERT_DIR/fullchain.pem" \
                        "$SSH_USER@$REMOTE_HOST:$LOCAL_CERT_DIR/"

                        echo "Fixing permissions"
                        ssh $SSH_OPTS "$SSH_USER@$REMOTE_HOST" \
                        "chmod 600 $LOCAL_CERT_DIR/syndicate.key $LOCAL_CERT_DIR/fullchain.pem"
                    '''
                }
            }
        }

        stage('Validate & reload NGINX') {
            steps {
                sshagent(['DEBIANSERVER']) {
                    sh '''
                        set -e

                        REMOTE_HOST=192.168.88.22
                        SSH_USER=funmicra
                        SSH_OPTS="-o StrictHostKeyChecking=no -o BatchMode=yes"

                        echo "Validating NGINX configuration"
                        ssh $SSH_OPTS "$SSH_USER@$REMOTE_HOST" \
                        "docker exec nginx-reverse-proxy nginx -t"

                        echo "Reloading NGINX"
                        ssh $SSH_OPTS "$SSH_USER@$REMOTE_HOST" \
                        "docker exec nginx-reverse-proxy nginx -s reload"
                    '''
                }
            }
        }
    }

post {
    always {
        withCredentials([
            string(credentialsId: 'TELEGRAM_BOT_TOKEN', variable: 'TELEGRAM_BOT_TOKEN'),
            string(credentialsId: 'TELEGRAM_CHAT_ID', variable: 'TELEGRAM_CHAT_ID')
        ]) {
            sh """
              rm -rf "${WORKSPACE}/certs" "${WORKSPACE}/vault.token"
              python3 telegram_notify.py \
                "${JOB_NAME}" \
                "${BUILD_NUMBER}" \
                "${currentBuild.currentResult}" \
                "${BUILD_URL}"
            """
            }
        }
    }
}