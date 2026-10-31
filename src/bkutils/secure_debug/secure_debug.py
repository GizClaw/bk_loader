import os
import json
import logging
import shutil
import re
import hashlib
import struct
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature, encode_dss_signature

def get_script_dir():
    script_dir = os.path.abspath(__file__)
    script_dir = os.path.dirname(script_dir)
    return script_dir

class SD:

    def __init__(self, pubkey_file='ec_256_pubkey.pem', privkey_file=None, uid='0000000000000000000000000000000000000000000000000000000000000000'):
        self.uid = uid
        self.bl1_rotpk_hash = ''
        self.sd_pk_hash = ''
        self.rotpk_hash_dict = {'bl1_rotpk_hash': '', 'sd_pk_hash': ''}
        script_dir = get_script_dir()
        self.tools_dir = f'{script_dir}/..'
        if pubkey_file == None:
            pubkey_file = f'{script_dir}/ec_256_pubkey.pem'
        if os.path.exists(pubkey_file) == False:
            raise FileNotFoundError(f'Public key file does not exist: {pubkey_file}')
        if privkey_file == None:
            sibling = os.path.join(os.path.dirname(os.path.abspath(pubkey_file)), 'ec_256_privkey.pem')
            privkey_file = sibling if os.path.isfile(sibling) else f'{script_dir}/ec_256_privkey.pem'
        # Public-key operations do not need a private key; signing opens it later.
        self.pubkey_file = pubkey_file
        self.privkey_file = privkey_file
        logging.debug(f'public key file: {pubkey_file}')

    def gen_rotpk_hash(self):
        self.gen_bl1_rotpk_hash()
        self.gen_sd_pk_hash()
        self.gen_rotpk_hash_json()
        return self.rotpk_hash_dict

    def gen_rotpk_hash_json(self):
        hash_json_file = 'rotpk_digest.json'
        with open(hash_json_file, 'w') as f:
            json.dump(self.rotpk_hash_dict, f, indent=4)
        logging.debug(f'generate {hash_json_file}')

    def gen_bl1_rotpk_hash(self):
        sh_sec_tools = f'{self.tools_dir}/tools/sh_sec_tools/secure_boot_tool'
        cmd = f'{sh_sec_tools} rotpk_hash -k {self.pubkey_file}'
        run_cmd(cmd)
        if os.path.exists('bl1_rotpk_digest.txt') == True:
            with open('bl1_rotpk_digest.txt', 'r') as f:
                self.bl1_rotpk_hash = f.read()
                self.bl1_rotpk_hash = self.reverse_order(self.bl1_rotpk_hash)
                self.rotpk_hash_dict['bl1_rotpk_hash'] = self.bl1_rotpk_hash
                logging.debug(f'bl1 rotpk hash={self.bl1_rotpk_hash}')
        else:
            logging.debug('bl1 digest bin not exists')
            exit(1)

    def reverse_order(self, hex_str):
        hex_str_len = len(hex_str)
        word_len = hex_str_len // 8
        reverse_str = ''
        for i in range(word_len):
            idx = i << 3
            reverse_str = reverse_str + hex_str[idx + 6]
            reverse_str = reverse_str + hex_str[idx + 7]
            reverse_str = reverse_str + hex_str[idx + 4]
            reverse_str = reverse_str + hex_str[idx + 5]
            reverse_str = reverse_str + hex_str[idx + 2]
            reverse_str = reverse_str + hex_str[idx + 3]
            reverse_str = reverse_str + hex_str[idx + 0]
            reverse_str = reverse_str + hex_str[idx + 1]
        logging.debug(f'hex_str={hex_str}')
        logging.debug(f'reverse_str={reverse_str}')
        return reverse_str

    def sha256(self, data):
        sha256_hash = hashlib.sha256()
        sha256_hash.update(data)
        sha256_hash = sha256_hash.hexdigest()
        return sha256_hash

    def gen_sd_pk(self):
        with open(self.pubkey_file, 'rt') as pem_file:
            pem_file_data = pem_file.read()
        try:
            public_key = serialization.load_pem_public_key(pem_file_data.encode())
            der_data = public_key.public_bytes(encoding=serialization.Encoding.DER, format=serialization.PublicFormat.SubjectPublicKeyInfo)
            uncompressed = public_key.public_bytes(encoding=serialization.Encoding.X962, format=serialization.PublicFormat.UncompressedPoint)
            self.sd_pk_len = len(uncompressed)
            self.sd_pk = uncompressed
            return (self.sd_pk, self.pubkey_file, self.privkey_file)
        except Exception as e:
            logging.debug(f'failed to load PEM data {e}')
            exit(1)

    def gen_sd_pk_hash(self):
        with open(self.pubkey_file, 'rt') as pem_file:
            pem_file_data = pem_file.read()
        try:
            public_key = serialization.load_pem_public_key(pem_file_data.encode())
            der_data = public_key.public_bytes(encoding=serialization.Encoding.DER, format=serialization.PublicFormat.SubjectPublicKeyInfo)
            uncompressed = public_key.public_bytes(encoding=serialization.Encoding.X962, format=serialization.PublicFormat.UncompressedPoint)
            self.sd_pk_len = len(uncompressed)
            self.sd_pk = uncompressed
            logging.debug(f'SD public key len={self.sd_pk_len}')
            logging.debug(f'SD public key={self.sd_pk}')
            self.sd_pk_hash = self.sha256(uncompressed)
            self.rotpk_hash_dict['sd_pk_hash'] = self.sd_pk_hash
            logging.debug(f'bl2 rotpk hash={self.sd_pk_hash}')
            with open('sd_digest.bin', 'wb+') as f:
                f.write(bytes.fromhex(self.sd_pk_hash))
        except Exception as e:
            logging.debug(f'failed to load PEM data {e}')
            exit(1)

    def sign_hash_bootrom(self, dat):
        with open(self.privkey_file, 'rb') as key_file:
            dat_hex = dat.hex()
            private_key = serialization.load_pem_private_key(key_file.read(), password=None, backend=default_backend())
            if not isinstance(private_key.curve, ec.SECP256R1):
                raise ValueError('The private key is not using secp256r1 curve')
            self.uid_sig = private_key.sign(bytes.fromhex(dat_hex), ec.ECDSA(hashes.SHA256()))
            self.uid_sig_size = len(self.uid_sig.hex())
            (r, s) = decode_dss_signature(self.uid_sig)
            self.uid_sig_r_s = (r, s)
            self.uid_sig_r = r
            self.uid_sig_r_bytes = r.to_bytes(32, 'big')
            self.uid_sig_s = s
            self.uid_sig_s_bytes = s.to_bytes(32, 'big')
            logging.debug(f'r_str={self.uid_sig_r_bytes.hex()}, s_str={self.uid_sig_r_bytes.hex()}')
            logging.debug(f'r={r}, s={s}')
            sig = self.uid_sig_r_bytes + self.uid_sig_s_bytes
            return (64, self.uid_sig, sig)

    def verify_hash(self, pubkey_path, data, signature):
        with open(pubkey_path, 'rb') as key_file:
            public_key = serialization.load_pem_public_key(key_file.read(), backend=default_backend())
        (r, s) = decode_dss_signature(signature)
        try:
            public_key.verify(encode_dss_signature(r, s), data, ec.ECDSA(hashes.SHA256()))
            return True
        except Exception as e:
            print(f'Verification failed: {e}')
            return False

    def sign_hash(self):
        hash_bytes = bytes.fromhex(self.uid)
        with open(self.privkey_file, 'rb') as key_file:
            private_key = serialization.load_pem_private_key(key_file.read(), password=None, backend=default_backend())
            if not isinstance(private_key.curve, ec.SECP256R1):
                raise ValueError('The private key is not using secp256r1 curve')
            self.uid_sig = private_key.sign(bytes.fromhex(self.uid), ec.ECDSA(hashes.SHA256()))
            self.uid_sig_size = len(self.uid_sig.hex())
            logging.debug(f'uid_sig_size = {self.uid_sig_size}')
            logging.debug(f'uid_sig = {self.uid_sig.hex()}')
            (r, s) = decode_dss_signature(self.uid_sig)
            self.uid_sig_r_s = (r, s)
            self.uid_sig_r = r
            self.uid_sig_r_bytes = r.to_bytes(32, 'big')
            self.uid_sig_s = s
            self.uid_sig_s_bytes = s.to_bytes(32, 'big')
            logging.debug(f'r_str={self.uid_sig_r_bytes.hex()}, s_str={self.uid_sig_r_bytes.hex()}')
            logging.debug(f'r={r}, s={s}')

    def create_sd_bin(self):
        with open('sd.bin', 'wb') as f:
            magic = struct.pack('<I', 2934619339)
            f.write(magic)
            pk_len = struct.pack('<I', self.sd_pk_len)
            f.write(pk_len)
            f.write(self.sd_pk)
            f.write(bytes.fromhex(self.uid))
            sig_len = struct.pack('<I', 64)
            f.write(sig_len)
            f.write(self.uid_sig_r_bytes)
            f.write(self.uid_sig_s_bytes)
if __name__ == '__main__':
    sd = SD('ec_256_pubkey.pem')
    sd.gen_sd_pk_hash()
    sd.sign_hash()
    sd.create_sd_bin()
