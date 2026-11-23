"""Cifrado de respaldos: AES-256-GCM por bloques con clave derivada por scrypt.

Formato MRLB v1:
  magic(6)="MRLB1\\n" | header_len(4, BE) | header JSON (salt, kdf params, chunk size, nonce prefix)
  bloques: len(4, BE) | ciphertext+tag
Cada bloque usa nonce = prefijo(8) + contador(4) y AAD = header + contador + flag de último bloque,
lo que impide reordenar, truncar o alterar bloques sin detección.
La frase de paso NUNCA se almacena."""
from __future__ import annotations

import base64
import json
import os
import struct
from pathlib import Path

from .errors import RpcError

MAGIC = b"MRLB1\n"
CHUNK = 1024 * 1024


def _require():
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
        return AESGCM, Scrypt
    except ImportError as e:
        raise RpcError("crypto_unavailable", "La biblioteca 'cryptography' no está instalada.") from e


def _derive(passphrase: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    _, Scrypt = _require()
    if len(passphrase) < 10:
        raise RpcError("weak_passphrase", "La frase de cifrado debe tener al menos 10 caracteres.")
    return Scrypt(salt=salt, length=32, n=n, r=r, p=p).derive(passphrase.encode("utf-8"))


def encrypt_file(src: Path, dst: Path, passphrase: str, *, n: int = 2**15) -> dict:
    AESGCM, _ = _require()
    salt, prefix = os.urandom(16), os.urandom(8)
    header = {"v": 1, "kdf": "scrypt", "n": n, "r": 8, "p": 1, "salt": base64.b64encode(salt).decode(),
              "cipher": "AES-256-GCM", "chunk": CHUNK, "noncePrefix": base64.b64encode(prefix).decode(),
              "name": Path(src).name}
    hbytes = json.dumps(header, sort_keys=True).encode()
    aes = AESGCM(_derive(passphrase, salt, n, 8, 1))
    tmp = Path(str(dst) + ".part")
    size = os.path.getsize(src)
    with open(src, "rb") as fi, open(tmp, "wb") as fo:
        fo.write(MAGIC + struct.pack(">I", len(hbytes)) + hbytes)
        idx, done = 0, 0
        while True:
            block = fi.read(CHUNK)
            done += len(block)
            last = done >= size
            ct = aes.encrypt(prefix + struct.pack(">I", idx), block, hbytes + struct.pack(">I?", idx, last))
            fo.write(struct.pack(">I", len(ct)) + ct)
            idx += 1
            if last:
                break
    os.replace(tmp, dst)
    return {"path": str(dst), "chunks": idx, "plainBytes": size}


def decrypt_file(src: Path, dst: Path, passphrase: str) -> dict:
    AESGCM, _ = _require()
    from cryptography.exceptions import InvalidTag
    tmp = Path(str(dst) + ".part")
    try:
        with open(src, "rb") as fi:
            if fi.read(len(MAGIC)) != MAGIC:
                raise RpcError("invalid_format", "El archivo no es un respaldo cifrado de MR Lab.")
            (hlen,) = struct.unpack(">I", fi.read(4))
            hbytes = fi.read(hlen)
            h = json.loads(hbytes)
            prefix = base64.b64decode(h["noncePrefix"])
            aes = AESGCM(_derive(passphrase, base64.b64decode(h["salt"]), h["n"], h["r"], h["p"]))
            idx, total, saw_last = 0, 0, False
            with open(tmp, "wb") as fo:
                while True:
                    raw = fi.read(4)
                    if not raw:
                        break
                    if saw_last:
                        raise RpcError("integrity_error", "Datos adicionales tras el último bloque.")
                    (clen,) = struct.unpack(">I", raw)
                    ct = fi.read(clen)
                    nonce = prefix + struct.pack(">I", idx)
                    try:
                        pt = aes.decrypt(nonce, ct, hbytes + struct.pack(">I?", idx, False))
                    except InvalidTag:
                        pt = aes.decrypt(nonce, ct, hbytes + struct.pack(">I?", idx, True))
                        saw_last = True
                    fo.write(pt)
                    total += len(pt)
                    idx += 1
            if not saw_last:
                raise RpcError("integrity_error", "El respaldo está truncado o incompleto.")
        os.replace(tmp, dst)
        return {"path": str(dst), "plainBytes": total}
    except InvalidTag as e:
        raise RpcError("decrypt_failed", "Frase incorrecta o respaldo alterado.") from e
    finally:
        if tmp.exists():
            tmp.unlink()
