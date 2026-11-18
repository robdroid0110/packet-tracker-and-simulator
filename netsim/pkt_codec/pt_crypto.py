from netsim.pkt_codec.eax import EAX
from netsim.pkt_codec.twofish import Twofish
import zlib
import struct

def deobf_stage1(data: bytes) -> bytes:
    L = len(data)
    return bytes(data[L-1-i] ^ (L - i*L & 0xFF) for i in range(L))

def deobf_stage2(data: bytes) -> bytes:
    L = len(data)
    return bytes(b ^ (L - i & 0xFF) for i, b in enumerate(data))

def uncompress_qt(blob: bytes) -> bytes:
    if len(blob) < 4:
        raise ValueError('Invalid compressed legacy lab data')
    size = struct.unpack(">I", blob[:4])[0]
    if size > 32_000_000:
        raise ValueError('legacy lab document exceeds 32 MB')
    decoder = zlib.decompressobj()
    result = decoder.decompress(blob[4:], size + 1)
    if len(result) != size or not decoder.eof:
        raise ValueError('Invalid compressed legacy lab document')
    return result

def decrypt_pkt(pkt: bytes) -> bytes:
    # Stage 1 deobfuscation
    stage1 = deobf_stage1(pkt)

    # Chiave e IV per i file .pkt
    key = bytes([137])*16
    iv  = bytes([16])*16

    # Twofish block cipher
    tf = Twofish(key)
    encrypt_block = tf.encrypt

    # EAX con nonce = iv
    eax = EAX(encrypt_block)

    # Supponiamo che negli .pkt il tag sia alla fine
    ciphertext = stage1[:-16]
    tag        = stage1[-16:]

    # Decrypt usando nonce fisso
    decrypted = eax.decrypt(nonce=iv, ciphertext=ciphertext, tag=tag)

    # Stage 2 deobfuscation
    stage2 = deobf_stage2(decrypted)

    # Decompressione
    xml = uncompress_qt(stage2)

    return xml

def encrypt_pkt(xml: bytes) -> bytes:
    """Encode a network XML document using the independently documented PT container.

    Byte layout reverses decrypt_pkt. This is file-interoperability encoding,
    not an implementation of the proprietary network simulation engine.
    """
    if not isinstance(xml, bytes) or len(xml) > 32_000_000:
        raise ValueError('PKT XML must be bytes smaller than 32 MB')
    blob = struct.pack('>I',len(xml)) + zlib.compress(xml,level=6)
    L = len(blob)
    inner = bytes(value ^ ((L-i)&255) for i,value in enumerate(blob))
    eax = EAX(Twofish(bytes([137])*16).encrypt)
    encrypted, tag = eax.encrypt(nonce=bytes([16])*16,plaintext=inner)
    stage1 = encrypted + tag
    L = len(stage1)
    out = bytearray(L)
    for i,value in enumerate(stage1):
        out[L-1-i] = value ^ ((L-i*L)&255)
    return bytes(out)
