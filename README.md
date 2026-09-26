# secure-file-app

Flask file-storage application integrated with Secure Key Lifecycle Manager (SKLM) using envelope encryption.

## Encryption architecture

For every uploaded file the application:

1. Generates a fresh 256-bit DEK with the operating-system CSPRNG.
2. Encrypts the file locally with AES-256-GCM.
3. Sends only the 32-byte DEK to SKLM over the authenticated KMS API.
4. SKLM wraps the DEK with the configured managed AES KEK using RFC 3394 AES Key Wrap.
5. Stores only ciphertext on disk and stores the wrapped DEK, nonce, KEK ID and KEK version in the application database.
6. On download, authorizes the user first, unwraps the DEK through SKLM, decrypts in memory and streams the original file to the authorized user.

The application does not store plaintext DEKs or plaintext KEKs in the database.

## Prerequisites

- Python 3.11+
- MySQL
- Secure Key Lifecycle Manager running on `127.0.0.1:8000`
- An ACTIVE AES-256 key in SKLM intended for Key Wrapping
- A dedicated SKLM service account with permission to read key metadata and call `crypto:use`

For local development you can temporarily use an existing Key Manager account, but do not use an Administrator credential in a deployed file service.

## Configuration

Copy `.env.example` to `.env` and update the values:

```powershell
Copy-Item .env.example .env
```

Important settings:

```env
DATABASE_URL=mysql+pymysql://secure_file_user:password@127.0.0.1:3306/secure_file
SKLM_BASE_URL=http://127.0.0.1:8000
SKLM_USERNAME=file-service
SKLM_PASSWORD=replace-me
SKLM_KEK_ID=KEY-REPLACE-ME
SKLM_VERIFY_TLS=false
```

For a real deployment, expose SKLM through HTTPS and set `SKLM_VERIFY_TLS=true`. Keep credentials outside source control.

## Database migration

The existing `files` table already contains `encryption_status`, `encryption_algorithm`, `kms_key_id`, and `kms_key_version`. Add the envelope-encryption fields with:

```powershell
python scripts/migrate_envelope_encryption.py
```

This adds:

- `wrapped_dek`
- `encryption_nonce`
- `key_wrap_algorithm`
- `ciphertext_sha256`

Existing plaintext files are left untouched and remain downloadable as legacy records. New uploads are encrypted.

## Run

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts/migrate_envelope_encryption.py
python app.py
```

Open:

- Secure File App: `http://127.0.0.1:5000`
- Health: `http://127.0.0.1:5000/health`
- Readiness with SKLM/KEK validation: `http://127.0.0.1:5000/ready`

## SKLM setup

Create one managed AES-256 key in SKLM, for example:

- Name: `Secure File App Master KEK`
- Alias: `secure-file-master-kek`
- Algorithm: `AES-256`
- Purpose: `Key Wrapping`
- Owner: `secure-file-app`

Put the generated `KEY-...` identifier into `SKLM_KEK_ID`.

Do not copy the raw key into this application. Secure File App needs only the key identifier and the SKLM API.

## Upload flow

```text
Browser -> Flask -> random DEK -> AES-256-GCM -> ciphertext on disk
                         |
                         +-> SKLM /api/crypto/wrap -> wrapped DEK in DB
```

## Download flow

```text
Authorized request -> DB wrapped DEK -> SKLM /api/crypto/unwrap
                                      -> DEK -> AES-GCM decrypt in memory
                                      -> original file response
```

## Key rotation

Files store both `kms_key_id` and `kms_key_version`. New uploads use the current active version. Existing files continue to unwrap with the version that originally protected their DEK. This means KEK rotation does not require re-encrypting the whole file.

Do not destroy an old SKLM key version while files still reference it, or those files will become undecryptable.
