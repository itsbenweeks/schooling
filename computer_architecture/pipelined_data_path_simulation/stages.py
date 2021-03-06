#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Benjamin Weeks
CS472 Project 3
November, 22nd, 2015
"""

from ctypes import c_short
from registers import *
from copy import deepcopy


class Memory(object):
    def __init__(self):
        self.memory = []
        for x in xrange(1024):
            self.memory.append(x & 0xFF)

    def __str__(self):
        result = ""
        x = 0
        for mem in self.memory:
            if x % 8 == 0:
                result += "\n"
            result += "{:>#5x},".format(mem)
            x += 1
        return result


class Registers(object):
    def __init__(self):
        self.registers = []
        for x in xrange(32):
            self.registers.append(x + 0x100)
        self.registers[0] = 0

    def __str__(self):
        result = ""
        x = 0
        for reg in self.registers:
            if x % 8 == 0:
                result += "\n"
            result += "{:>#6x},".format(reg)
            x += 1
        return result


class Pipeline(object):
    def __init__(self):
        self.ifidregisters = []
        self.idexregisters = []
        self.exmemregisters = []
        self.memwbregisters = []
        self.main_memory = Memory()
        self.cache_registers = Registers()

        for x in xrange(2):
            self.ifidregisters.append(IFIDRegister())
            self.idexregisters.append(IDEXRegister())
            self.exmemregisters.append(EXMEMRegister())
            self.memwbregisters.append(MEMWBRegister())

    def _alu_control(self, function=0b100000, alu_op=0b10):
        if function is None:
            if alu_op == 00:
                return 0b0010
            else:
                return 0b0110
        if function == 0b100000:
            return 0b0010
        elif function == 0b100010:
            return 0b0110
        elif function == 0b100100:
            return 0b0000
        elif function == 0b100101:
            return 0b0001
        elif function == 0b101010:
            return 0b0111

    def _alu(self, data1, data2, alu_control=0b0010):
        if alu_control == 0b0000:
            return data1 and data2
        elif alu_control == 0b0001:
            return data1 or data2
        elif alu_control == 0b0010:
            return data1 + data2
        elif alu_control == 0b0110:
            return data1 - data2
        elif alu_control == 0b0111:
            return data1 < data2
        else:
            return data1 + data2

    def if_stage(self, instruction_cache, pc):
        """
        IF You will fetch the next instruction out of the Instruction Cache.
        Put it in the WRITE version of the IF/ID pipeline register.
        """
        w_register = self.ifidregisters[0]
        instruction = instruction_cache[pc]
        if instruction_cache[pc] == 0:
            w_register.function = 0
            w_register.opcode = None
            return

        opcodes = {
            0x20: 'lb',
            0x28: 'sb',
        }
        functions = {
            0x20: 'add',
            0x22: 'sub',
            0: 'nop'
        }

        opcode_mask = 0b111111 << 26
        src1reg_mask = 0b11111 << 21
        src2reg_mask = 0b11111 << 16
        destreg_mask = 0b11111 << 11
        function_mask = 0b111111
        offset_mask = 0xffff
        pc += 4
        opcode = (instruction & opcode_mask) >> 26
        src1reg = (instruction & src1reg_mask) >> 21
        src2reg = (instruction & src2reg_mask) >> 16
        destreg = (instruction & destreg_mask) >> 11
        function = instruction & function_mask
        offset = c_short(instruction & offset_mask).value

        w_register.incr_pc = pc
        w_register.inst = instruction

        if not opcode:
            w_register.opcode = None
            w_register.function = function
            w_register.mips_inst = "{} ${}, ${}, ${}".format(
                functions[function],
                destreg,
                src1reg,
                src2reg)

        else:
            w_register.opcode = opcode
            w_register.function = None
            w_register.mips_inst = "{} ${}, {}(${})".format(
                opcodes[opcode],
                src2reg,
                offset,
                src1reg)

        return

    def id_stage(self):
        """
        ID Here you'll read an instruction from the READ version of IF/ID
        pipeline register, do the decoding and register fetching and write the
        values to the WRITE version of the ID/EX pipeline register.
        """
        r_register = self.ifidregisters[1]
        w_register = self.idexregisters[0]
        registers = self.cache_registers.registers

        if r_register.function == 0:
            w_register.function = r_register.function
            w_register.opcode = None
            return

        w_register.function = r_register.function
        w_register.opcode = r_register.opcode
        w_register.incr_pc = r_register.incr_pc
        src1reg_mask = 0b11111
        src2reg_mask = src1reg_mask
        destreg_mask = src1reg_mask
        offset_mask = 0xffff
        src1reg = (r_register.inst >> 21) & src1reg_mask
        src2reg = (r_register.inst >> 16)  & src2reg_mask
        destreg = (r_register.inst >> 11) & destreg_mask
        offset = c_short(r_register.inst & offset_mask).value
        w_register.read_reg1_value = self.cache_registers.registers[src1reg]
        w_register.read_reg2_value = registers[src2reg]
        w_register.write_reg_15_11 = destreg
        w_register.write_reg_20_16 = src2reg

        if r_register.opcode is None:  # R-Type
            w_register.reg_dst = True
            w_register.alu_src = False
            w_register.mem_read = False
            w_register.mem_write = False
            w_register.mem_to_reg = False
            w_register.reg_write = True
            w_register.branch = False
            w_register.se_offset = None
            w_register.alu_op = (r_register.inst >> 4) & 0b11

        elif "lb" in r_register.mips_inst:
            w_register.reg_dst = False
            w_register.alu_src = True
            w_register.mem_read = True
            w_register.mem_write = False
            w_register.mem_to_reg = True
            w_register.reg_write = True
            w_register.branch = False
            w_register.se_offset = offset
            w_register.alu_op = 0

        elif "sb" in r_register.mips_inst:
            w_register.reg_dst = 0
            w_register.alu_src = True
            w_register.mem_read = False
            w_register.mem_write = True
            w_register.mem_to_reg = None
            w_register.reg_write = False
            w_register.branch = False
            w_register.se_offset = offset
            w_register.alu_op = 0

        return

    def ex_stage(self):
        """
        EX Here you'll perform the requested instruction on the specific
        operands you read out of the READ version of the IDEX pipeline register
        and then write the appropriate values to the WRITE version of the EX/MEM
        pipeline register. For example, an “add” operation will take the two
        operands out of the ID/EX pipeline register and add them together like
        this:
            EX_MEM_WRITE.ALU_Result = ID_EX_READ.Reg_Val1 + ID_EX_READ.Reg_Val2;
        """
        r_register = self.idexregisters[1]
        w_register = self.exmemregisters[0]
        w_register.function = r_register.function
        w_register.opcode = r_register.opcode

        if w_register.function == 0:
            return

        w_register.incr_pc = r_register.incr_pc
        w_register.mem_read = r_register.mem_read
        w_register.mem_write = r_register.mem_write
        w_register.reg_write = r_register.reg_write
        w_register.mem_to_reg = r_register.mem_to_reg
        data1 = r_register.read_reg1_value
        data2 = 0
        # Mux the offset or the data register
        if r_register.alu_src:
            data2 = r_register.se_offset
        else:
            data2 = r_register.read_reg2_value

        # Perform in the main ALU
        alu_op = r_register.alu_op
        control_sig = r_register.function
        alu_control = self._alu_control(control_sig, alu_op)
        w_register.alu_result = self._alu(data1, data2, alu_control)
        w_register.zero = w_register.alu_result == 0
        if r_register.se_offset is not None:
            w_register.calc_bta = r_register.incr_pc + (r_register.se_offset << 2)

        # Pass it on
        w_register.sw_value = r_register.read_reg2_value

        # Determine the write register
        if r_register.reg_dst:
            w_register.write_reg_num = r_register.write_reg_15_11
        else:
            w_register.write_reg_num = r_register.write_reg_20_16

        return

    def mem_stage(self):
        """
        MEM If the instruction is a lb, then use the address you calculated in
        the EX stage as an index into your Main Memory array and get the value
        that is there. Otherwise, just pass information from the READ version of
        the EX_MEM pipeline register to the WRITE version of MEM_WB.
        """
        r_register = self.exmemregisters[1]
        w_register = self.memwbregisters[0]
        main_memory = self.main_memory.memory

        w_register.reg_write = r_register.reg_write
        w_register.alu_result = r_register.alu_result
        w_register.write_reg_num = r_register.write_reg_num
        w_register.function = r_register.function
        w_register.opcode = r_register.opcode

        if w_register.function == 0:
            return

        if r_register.mem_read:
            w_register.lw_data_value = deepcopy(main_memory[r_register.alu_result])
        else:
            w_register.lw_data_value = None

        if r_register.mem_write:
            print "writing {} to mem addr {}".format(hex(r_register.sw_value),r_register.alu_result)
            main_memory[r_register.alu_result] = deepcopy(r_register.sw_value)
            pass

        return

    def wb_stage(self):
        """
        WB Write to the registers based on information you read out of the
        READ version of MEM_WB.
        """
        r_register = self.memwbregisters[1]
        registers = self.cache_registers.registers

        if r_register.function == 0:
            return

        if r_register.reg_write:
            if r_register.mem_to_reg:
                print "writing {} to reg addr {}".format(hex(r_register.lw_data_value),r_register.write_reg_num)
                registers[r_register.write_reg_num] = deepcopy(r_register.lw_data_value)
            else:
                print "writing {} to reg addr {}".format(hex(r_register.alu_result),r_register.write_reg_num)
                registers[r_register.write_reg_num] = deepcopy(r_register.alu_result)
        return

    def print_out_everything(self):
        # print "{:*^72}".format("Main Memory")
        # print str(self.main_memory)
        print "{:*^72}".format("Registers")
        print str(self.cache_registers)
        print "{:*^72}".format("IF/ID Write Register")
        print str(self.ifidregisters[0])
        print "{:*^72}".format("IF/ID Read Register")
        print str(self.ifidregisters[1])
        print "{:*^72}".format("ID/EX Write Register")
        print str(self.idexregisters[0])
        print "{:*^72}".format("ID/EX Read Register")
        print str(self.idexregisters[1])
        print "{:*^72}".format("EX/MEM Write Register")
        print str(self.exmemregisters[0])
        print "{:*^72}".format("EX/MEM Read Register")
        print str(self.exmemregisters[1])
        print "{:*^72}".format("MEM/WB Write Register")
        print str(self.memwbregisters[0])
        print "{:*^72}".format("MEM/WB Read Register")
        print str(self.memwbregisters[1])
        return

    def copy_write_to_read(self):
        self.ifidregisters[1] = deepcopy(self.ifidregisters[0])
        self.idexregisters[1] = deepcopy(self.idexregisters[0])
        self.exmemregisters[1]  = deepcopy(self.exmemregisters[0])
        self.memwbregisters[1]  = deepcopy(self.memwbregisters[0])
        return
