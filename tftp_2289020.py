#!/usr/bin/python3
import socket
import argparse
from struct import pack

DEFAULT_PORT = 69
BLOCK_SIZE = 512
DEFAULT_TRANSFER_MODE = 'octet'
TIMEOUT = 5

OPCODE = {'RRQ': 1, 'WRQ': 2, 'DATA': 3, 'ACK': 4, 'ERROR': 5}

ERROR_CODE = {
    0: "Not defined, see error message (if any).",
    1: "File not found.",
    2: "Access violation.",
    3: "Disk full or allocation exceeded.",
    4: "Illegal TFTP operation.",
    5: "Unknown transfer ID.",
    6: "File already exists.",
    7: "No such user."
}

def send_wrq(filename, mode, sock, server_address):
    format = f'>h{len(filename)}sB{len(mode)}sB'
    wrq_message = pack(format, OPCODE['WRQ'], bytes(filename, 'utf-8'), 0, bytes(mode, 'utf-8'), 0)
    sock.sendto(wrq_message, server_address)

def send_rrq(filename, mode, sock, server_address):
    format = f'>h{len(filename)}sB{len(mode)}sB'
    rrq_message = pack(format, OPCODE['RRQ'], bytes(filename, 'utf-8'), 0, bytes(mode, 'utf-8'), 0)
    sock.sendto(rrq_message, server_address)

def tftp_put(filename, sock, server_address):
    sock.settimeout(TIMEOUT)
    send_wrq(filename, DEFAULT_TRANSFER_MODE, sock, server_address)

    try:
        ack, address = sock.recvfrom(4)
    except socket.timeout:
        print("타임아웃: 서버로부터 WRQ에 대한 응답이 없습니다. 종료합니다.")
        return

    with open(filename, 'rb') as file:
        block_number = 1
        while True:
            file_block = file.read(BLOCK_SIZE)
            if not file_block:
                break

            data_packet = pack(f'>hh{len(file_block)}s', OPCODE['DATA'], block_number, file_block)
            sock.sendto(data_packet, address)

            try:
                ack, address = sock.recvfrom(4)
                ack_opcode = int.from_bytes(ack[:2], 'big')
                ack_block_number = int.from_bytes(ack[2:], 'big')

                if ack_opcode == OPCODE['ACK'] and ack_block_number == block_number:
                    block_number += 1
            except socket.timeout:
                print("타임아웃: 파일 업로드 중 서버로부터 응답이 없습니다. 다시 시도합니다...")
                continue

def tftp_get(filename, sock, server_address):
    sock.settimeout(TIMEOUT)
    send_rrq(filename, DEFAULT_TRANSFER_MODE, sock, server_address)

    try:
        data, address = sock.recvfrom(516)
    except socket.timeout:
        print("타임아웃: 서버로부터 RRQ에 대한 응답이 없습니다. 종료합니다.")
        return

    with open(filename, 'wb') as file:
        block_number = 1
        while True:
            opcode = int.from_bytes(data[:2], 'big')
            if opcode == OPCODE['DATA']:
                block = int.from_bytes(data[2:4], 'big')
                if block == block_number:
                    file.write(data[4:])
                    send_ack(block, sock, address)
                    block_number += 1

                if len(data[4:]) < BLOCK_SIZE:
                    break
            elif opcode == OPCODE['ERROR']:
                error_code = int.from_bytes(data[2:4], 'big')
                print(f"Error: {ERROR_CODE.get(error_code, 'Unknown error')}")
                break
            else:
                break

            try:
                data, address = sock.recvfrom(516)
            except socket.timeout:
                print("타임아웃: 파일 다운로드 중 서버로부터 응답이 없습니다. 종료합니다.")
                break

def send_ack(block_number, sock, address):
    ack_packet = pack(f'>hh', OPCODE['ACK'], block_number)
    sock.sendto(ack_packet, address)

parser = argparse.ArgumentParser(description="TFTP client program")
parser.add_argument("host", help="Server IP address", type=str)
parser.add_argument("operation", help="get or put command", type=str)
parser.add_argument("filename", help="File name to transfer", type=str)
parser.add_argument("-p", "--port", help="Server port number", type=int, default=DEFAULT_PORT)
args = parser.parse_args()

server_ip = args.host
server_port = args.port
server_address = (server_ip, server_port)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

if args.operation.lower() == "get":
    tftp_get(args.filename, sock, server_address)
elif args.operation.lower() == "put":
    tftp_put(args.filename, sock, server_address)
else:
    print("Invalid command. Use 'get' or 'put'.")

sock.close()