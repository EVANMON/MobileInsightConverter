#!/usr/bin/env python3
# Author: Zhen Feng

from collections import OrderedDict
import xml.etree.ElementTree as ET

class DlTxDelayAnalyzer():
    def __init__(self):
        self.txdelay = 0.0
        self.totatPackets = 0
        self.PDCP_packets = []
        self.RLC_packets = []   # sorted by descending timestamp
        self.MAC_packets = []
        self.PHY_packets = []

    def analyze(self):
        self.firstTime = PDCP_packets[-1].time_stamp
        for PDCP_packet in PDCP_packets:
            d = self.PDCP_delay(PDCP_packet)
            print('delay: ' + str(d) + ' frame')
            self.txdelay += d
        return self.txdelay / self.totatPackets

    def PDCP_delay(self, PDCP_packet):
        firstRLC = self.first_RLC_of_PDCP(PDCP_packet.time_stamp)
        self.totatPackets = len(PDCP_packets)
        if not firstRLC:
            self.totatPackets -= 1
            return 0
        firstPHY = self.first_PHY_of_RLC(firstRLC.time_stamp)
        if not firstPHY:
            self.totatPackets -= 1
            return 0
        
        result = PDCP_packet.time_stamp - firstPHY.time_stamp
        del firstPHY
        return result
        
    def first_RLC_of_PDCP(self, PDCP_time_stamp):
        i = 0
        while self.RLC_packets[i].time_stamp > PDCP_time_stamp:
            i += 1
        for RLC_packet in RLC_packets[i:]:
            if RLC_packet.find_value("FI")[0] == "0":
                return RLC_packet
        return None

    def first_PHY_of_RLC(self, RLC_time_stamp):
        i = 0
        while self.PHY_packets[i].time_stamp > RLC_time_stamp:
            i += 1
        #assert self.PHY_packets[i].time_stamp == RLC_time_stamp
        lastNDI = self.PHY_packets[i].find_value("NDI")
        lastHarqId = self.PHY_packets[i].find_value("HARQ ID")
        for PHY_packet in PHY_packets[i+1:]:
            if PHY_packet.find_value("HARQ ID") == lastHarqId and PHY_packet.find_value("NDI") != lastNDI:
                return PHY_packet
        return None


class AtomPacket(object):
    def __init__(self, information_dict, time_stamp, packet_type):
        self.information_dict = information_dict
        self.time_stamp = time_stamp
        self.type = packet_type

    def find_value(self, key):
        return self.information_dict.get(key, None)

    def __str__(self):
        result = ["time_stamp", str(self.time_stamp), "type", str(self.type), "information", str(self.information_dict)]
        return " ".join(result)

    def __repr__(self):
        return self.__str__()


class MobileInsightXmlToListConverter(object):

    @staticmethod
    def convert_xmltree_to_dict(root, current_dict):
        """
        convert xml_element to dictionary where each value can be
        a pure value or a dict or list of dict
        example:
        <dm_log_packet>
            <pair key="log_msg_len">436</pair>
            <pair key="type_id">LTE_PHY_PDSCH_Stat_Indication</pair>
            <pair key="timestamp">2017-11-16 23:48:06.186771</pair>
            <pair key="Records" type="list">
                <list>
                    <item type="dict">
                        <dict>
                            <pair key="Subframe Num">6</pair>
                            <pair key="Frame Num">78</pair>
                            <pair key="Num RBs">3</pair>
                        </dict>
                    </item>
                </list>
            </pair>
        <dm_log_packet>

        dict:
        {   "log_msg_len":436,
            "type_id": "LTE_PHY_PDSCH_Stat_Indication",
            "timestamp": "2017-11-16 23:48:06.186771",
            "records": [{"Subframe":6, "Frame Num": 78, "Num RBs": 3}]
        }

        :param root: current xml root
        :param current_dict: the dictionary that current level
               xml elements will be added in
        :return: None
        """
        for child in root:
            if "type" in child.attrib and child.attrib["type"] == "list":
                list_result = []
                current_dict[child.attrib["key"]]=list_result
                list_of_elements = child[0]
                for element in list_of_elements:
                    if "type" in element.attrib and element.attrib["type"] == "dict":
                        dict_root = element[0]
                        new_dict = OrderedDict()
                        MobileInsightXmlToListConverter.convert_xmltree_to_dict(dict_root, new_dict)
                    list_result.append(new_dict)
            else:
                current_dict[child.attrib["key"]] = child.text

    @staticmethod
    def print_dict(current_dict, number_space):
        """
        print value inside a dict
        :param current_dict: the dict that needs to be printed
        :param number_space: initial number of space before starting to print
        :return:
        """
        for key, value in current_dict.items():
            if isinstance(value, str):
                print("  "*number_space, key, value)
            else:
                print("  " * number_space, key, ":")
                for element in value:
                    MobileInsightXmlToListConverter.print_dict(element, number_space+1)

    @staticmethod
    def convert_xml_to_list(xml_file):
        """

        parse out list of packets from mobile insight log file

        :param xml_file: file that needs to be parsed
        :return:
        """
        tree = ET.parse(xml_file)
        root = tree.getroot()

        PDCP_packets, RLC_packets, PHY_packets, counter, global_fn = \
        [],           [],          [],          0,       None

        for child in root:
            new_dict = {}
            MobileInsightXmlToListConverter.convert_xmltree_to_dict(child, new_dict)

            if "type_id" in new_dict and new_dict[
                "type_id"] == "LTE_PDCP_DL_Cipher_Data_PDU":
                subpackets = new_dict["Subpackets"]
                for subpacket in subpackets:
                    datas = subpacket["PDCPDL CIPH DATA"]
                    for data in datas:
                        # if not prev_stamp or prev_stamp != time_stamp:
                        #   PDCP_counter+=1
                        #   prev_stamp = time_stamp
                        if not global_fn:
                            global_fn = int(data["Sys FN"])
                        elif global_fn > int(data["Sys FN"]):
                            counter += 1
                        global_fn = int(data["Sys FN"])
                        time_stamp = float(
                            '.'.join((data["Sys FN"], data["Sub FN"])))
                        time_stamp += counter * 1024
                        current_packet = AtomPacket(data, time_stamp, "PDCP")
                        PDCP_packets.append(current_packet)

            elif "type_id" in new_dict and new_dict[
                "type_id"] == "LTE_RLC_DL_AM_All_PDU":
                subpackets = new_dict["Subpackets"]
                for subpacket in subpackets:
                    datas = subpacket["RLCDL PDUs"]
                    prev_stamp = None
                    for data in datas:
                        # only collect the actual data instead of control data
                        if data["PDU TYPE"] == "RLCDL DATA":
                            if not global_fn:
                                global_fn = int(data["sys_fn"])
                            elif global_fn > int(data["sys_fn"]):
                                counter += 1
                            global_fn = int(data["sys_fn"])
                            time_stamp = float(
                                '.'.join((data["sys_fn"], data["sub_fn"])))
                            time_stamp += counter * 1024
                            current_packet = AtomPacket(data, time_stamp, "RLC")
                            RLC_packets.append(current_packet)
            elif "type_id" in new_dict and new_dict[
                "type_id"] == "LTE_PHY_PDSCH_Stat_Indication":
                records = new_dict["Records"]
                for record in records:
                    if not global_fn:
                        global_fn = int(record["Frame Num"])
                    elif global_fn > int(record["Frame Num"]):
                        counter += 1
                    global_fn = int(record["Frame Num"])
                    time_stamp = float(
                        '.'.join((record["Frame Num"], record["Subframe Num"])))
                    time_stamp += counter * 1024
                    transport_blocks = record["Transport Blocks"]
                    for transport_block in transport_blocks:
                        current_packet = AtomPacket(transport_block, time_stamp,
                                                    "PHY")
                        PHY_packets.append(current_packet)

            else:
                print("packets cannot clarify, packets <%s - %s - %s> drops" % (
                    new_dict["timestamp"], new_dict["Version"],
                    new_dict["log_msg_len"]))

        RLC_packets.sort(key=lambda packet: packet.time_stamp, reverse=True)
        PDCP_packets.sort(key=lambda packet: packet.time_stamp, reverse=True)
        PHY_packets.sort(key=lambda packet: packet.time_stamp, reverse=True)

        return RLC_packets, PDCP_packets, PHY_packets


RLC_packets, PDCP_packets, PHY_packets = MobileInsightXmlToListConverter.convert_xml_to_list("clash_royale.txt")


analyzer = DlTxDelayAnalyzer()

print(len(PDCP_packets))
analyzer.PDCP_packets = PDCP_packets
analyzer.RLC_packets = RLC_packets # sorted by descending timestamp
analyzer.PHY_packets = PHY_packets
analyzer.analyze()
# for packet in RLC_packets:
#     print(packet)
#
# for packet in PHY_packets:
#     print(packet)
#
# for packet in PDCP_packets:
#     print(packet)

# result_list = []
# for child in root:
#     new_dict = OrderedDict()
#     parse_xml(child, new_dict)
#     result_list.append(new_dict)
#
#
# for element in result_list:
#     print_dict(element, 0)


