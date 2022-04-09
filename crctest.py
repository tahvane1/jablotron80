import crccheck

class Message():
    poly=0
    init_value=0
    final_xor_value=0x00
    reverse_input=False
    reverse_output=False
    sequenced_finds = 0

    @classmethod
    def check_crc(cls, packet: bytes) -> bool:

        found = False
        found_immediately = True

        length = len(packet)
        assert packet[length-1] == 0xff
        expected_checksum = packet[length-2]
        data = packet[:length-2]

        for final_xor_value in range(cls.final_xor_value, 0x100):
            for init_value in range(cls.init_value, 0x100):
                for poly in range(cls.poly, 0x100):
                    configuration = crccheck.crc.Crc(8, poly, initvalue=init_value, xor_output=final_xor_value, reflect_input=cls.reverse_input, reflect_output=cls.reverse_output)
                    checksum = configuration.calc(data)

                    if checksum & 0x7f == expected_checksum:
                        found = True
                        if cls.sequenced_finds > 2:
                            print(f'found:{cls.sequenced_finds}, poly: {poly}, init: {init_value}, final:{final_xor_value}, revin:{cls.reverse_input}, revout:{cls.reverse_output}')
                        break
                    else:
                        cls.sequenced_finds = 0

                    found_immediately = False

                if found == True:
                    break
                else:
                    cls.poly = 0

            if found == True:
                break
            else:
                cls.init_value = 0

        if found_immediately:
            cls.sequenced_finds +=1
        else:
            cls.sequenced_finds = 0

        if found == False:
            print(f'not found, switching directions')

            if cls.reverse_input and cls.reverse_output:
                exit()
            else:
                poly=0
                init_value=0x00
                final_xor_value=0x00
            
            if cls.reverse_input == False:
                cls.reverse_input = True
            elif cls.reverse_output == False:
                cls.reverse_output = True
                cls.reverse_input = False

        cls.poly=poly
        cls.init_value=init_value
        cls.final_xor_value=final_xor_value

        return True

messages = ['a','b','c','d','e','f','g','h','i']
#messages[0] = b'\xed\x40\x00\x00\x01\x00\x00\x00\x16\xff'
#messages[1] = b'\xed\x40\x00\x00\x01\x00\x00\x0a\x26\xff'
#messages[2] = b'\xed\x40\x00\x00\x01\x00\x00\x14\x76\xff'
#messages[3] = b'\xed\x40\x00\x00\x01\x00\x00\x1e\x46\xff'
messages[8] = b'\xe7\x09\x04\x14\x06\x42\x3f\x6c\xff'

messages[7] = b'\xed\x40\x00\x00\x01\x00\x00\x32\x7b\xff'
messages[6] = b'\xed\x40\x04\x00\x01\x00\x00\x00\x4b\xff'
messages[5] = b'\xed\x51\x0c\x00\x09\x00\x00\x00\x05\xff'
messages[4] = b'\xed\x51\x0c\x00\x09\x00\x00\x1e\x55\xff'

messages[0] = b'\xe6\x06\x01\x03\x06\x01\x03\x2b\xff'
messages[1] = b'\xe6\x06\x01\x03\x07\x01\x03\x67\xff'
messages[2] = b'\xe6\x06\x01\x03\x08\x01\x03\x29\xff'
messages[3] = b'\xe6\x06\x01\x03\x09\x01\x03\x65\xff'

while True:
    for message in messages:
        Message.check_crc(message)