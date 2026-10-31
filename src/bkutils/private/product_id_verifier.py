from bkutils.common.common import crc32bytes, BinInfo

def verify_chip_product_id_private(binfile: BinInfo, read_chip_otp_func, otp_ahb_base_addr):
    """
    验证芯片产品ID的私有方法
    
    功能概述：
        从bin文件中读取16字节的产品ID（偏移量0x108或0x118，取决于是否有CRC），
        与OTP中的产品ID（AHB偏移量0x58c~0x59c）进行比较验证。
    
    参数说明：
        binfile: BinInfo对象，包含bin文件信息（pfile属性为文件二进制数据）
        read_chip_otp_func: 读取芯片OTP的函数，签名应为 func(addr, length) -> (bytes, msg)
        otp_ahb_base_addr: OTP的AHB基地址
    
    返回值：
        None - 验证通过或跳过验证时返回None
    
    异常：
        Exception: 当OTP读取失败或产品ID验证失败时抛出异常
    
    逻辑流程：
        1. 确定bin文件中的产品ID偏移量（0x100或0x110）
        2. 检查magic words是否为'BEKEN'
        3. 读取bin文件中的产品ID（16字节）
        4. 如果bin中的ID全为0，跳过验证
        5. 从OTP读取产品ID（16字节）
        6. 如果OTP中的ID全为0或为'BK7239N'开头，跳过验证
        7. 比较OTP ID和bin ID中'Q'字符之前的部分
        8. 如果不匹配，抛出异常
    """
    offset = 256
    if crc32bytes(binfile.pfile[0:32]) == bytearray(binfile.pfile[0:34]):
        offset = 272
    magicwords = binfile.pfile[offset:offset + 5]
    if magicwords != b'BEKEN':
        return
    binid = binfile.pfile[offset + 8:offset + 8 + 16]
    if binid == b'\x00' * 16:
        return
    (otpid, msg) = read_chip_otp_func(otp_ahb_base_addr + 1420, 16)
    if otpid is None:
        raise Exception(f'read chip otp fail: 0x{otp_ahb_base_addr + 1420}')
    if otpid == b'\x00' * 16 or otpid[:7] == b'BK7239N' or otpid[:7] == b'BK7236N':
        return
    otpid_q_pos = otpid.find(b'Q')
    otpid_part = otpid[:otpid_q_pos] if otpid_q_pos != -1 else otpid
    binid_part = binid[:otpid_q_pos] if otpid_q_pos != -1 else binid
    if otpid_part != binid_part:
        raise Exception('verify the product id fail, stop download.')
