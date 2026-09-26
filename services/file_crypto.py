import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


AES_GCM_NONCE_BYTES = 12


def generate_dek() -> bytes:
    """Generate a fresh AES-256 data-encryption key for one file."""
    return AESGCM.generate_key(bit_length=256)


def encrypt_file_data(plaintext: bytes, dek: bytes) -> tuple[bytes, bytes]:
    nonce = os.urandom(AES_GCM_NONCE_BYTES)
    ciphertext = AESGCM(dek).encrypt(nonce, plaintext, None)
    return ciphertext, nonce


def decrypt_file_data(ciphertext: bytes, dek: bytes, nonce: bytes) -> bytes:
    return AESGCM(dek).decrypt(nonce, ciphertext, None)
