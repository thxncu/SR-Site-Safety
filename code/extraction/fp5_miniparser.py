"""Minimal FileMaker (FP5/.fp2/.KSE runtime) table reader.

METHODS RECORD. Supports build_covered_elsewhere_audit.py by decoding the
legacy FileMaker runtime tables. Not needed to reproduce the manuscript
numbers from data/.
"""
from __future__ import annotations
from pathlib import Path
from collections import OrderedDict, defaultdict
import struct


def decode_vli(src: bytes, subtract_64: bool=False) -> int:
    n=len(src)
    if n==1 and 0x00 <= src[0] <= 0x7F:
        return src[0] - (0x40 if subtract_64 else 0)
    if n==1 and src[0]>=0x80:
        return src[0]
    if n==2 and 0x80 <= src[0] <= 0xBF:
        return 0x80 + (src[0]-0x80)*0x100 + src[1]
    if n==3 and 0xC0 <= src[0] <= 0xDF:
        return 0x4080 + (src[0]-0xC0)*0x10000 + src[1]*0x100 + src[2]
    if n==4 and 0xE0 <= src[0] <= 0xEF:
        return 0x204080 + (src[0]-0xE0)*0x1000000 + src[1]*0x10000 + src[2]*0x100 + src[3]
    if n==5 and 0xF0 <= src[0] <= 0xF7:
        return 0x10204080 + (src[0]-0xF0)*0x100000000 + src[1]*0x1000000 + src[2]*0x10000 + src[3]*0x100 + src[4]
    return int.from_bytes(src,'big')

class FP5MiniParser:
    def __init__(self, path):
        self.path=Path(path)
        self.data=self.path.read_bytes()
        if len(self.data)%0x400: raise ValueError('size not sector multiple')
        self.maxlevel=struct.unpack('>B',self.data[0x801:0x802])[0]
        self.largest=struct.unpack('>I',self.data[0x806:0x80a])[0]
        self.first_pos={self.maxlevel:0x800}
        self.length=defaultdict(int); self.length[self.maxlevel]=1
        self.prev_to_pos={}
        self.orders={}; self.id_to_pos={}
        self._scan_blocks(); self._order_blocks()
        self.root=None
        self.stats=defaultdict(int)

    def _scan_blocks(self):
        for off in range(0xC00,len(self.data),0x400):
            deleted, level, prev=struct.unpack('>BBI',self.data[off:off+6])
            if deleted==0xff: continue
            self.length[level]+=1
            if prev==0 and level not in self.first_pos: self.first_pos[level]=off
            if prev in self.prev_to_pos:
                if prev!=0: raise ValueError(f'duplicate prev id {prev}')
            else:
                self.prev_to_pos[prev]=off
        self.root_pos={}
        for off in range(0x800,len(self.data),0x400):
            deleted, level, prev=struct.unpack('>BBI',self.data[off:off+6])
            if deleted!=0xff and prev==0 and level not in self.root_pos:
                self.root_pos[level]=off

    def _first_block_ref(self, level):
        pos=self.id_to_pos[self.orders[level][0]]
        x=self.data[pos+14:pos+20]
        if x[:2]!=b'\x00\x04': raise ValueError((level,pos,x.hex()))
        return int.from_bytes(x[2:],'big')

    def _order_blocks(self):
        for level in reversed(range(self.maxlevel+1)):
            if level==self.maxlevel:
                self.orders[level]=[0]
                self.id_to_pos[0]=self.first_pos[level]
                continue
            next_prev=self._first_block_ref(level+1)
            current_prev=0
            prev_next=0
            order=[]
            for _ in range(self.length[level]):
                if next_prev is None: break
                block_pos=self.root_pos[level] if current_prev==0 else self.prev_to_pos[current_prev]
                current_next=struct.unpack('>I',self.data[block_pos+6:block_pos+10])[0]
                if current_next!=0:
                    next_pos=self.prev_to_pos[next_prev]
                    next_prev=struct.unpack('>I',self.data[next_pos+2:next_pos+6])[0]
                else:
                    next_prev=None
                if next_prev is not None:
                    current_id=next_prev
                    next_prev=current_next
                else:
                    current_id=prev_next
                    next_prev=None
                self.id_to_pos[current_id]=block_pos
                order.append(current_id)
                current_prev=current_id
                prev_next=current_next
            if len(order)!=self.length[level]:
                raise ValueError(f'order mismatch level {level}: {len(order)} != {self.length[level]}')
            self.orders[level]=order

    def parse_tree(self):
        root=OrderedDict(); current=root; stack=[]; path=[]; current_bytes=None
        first=True
        for bi, block_id in enumerate(self.orders[0]):
            pos=self.id_to_pos[block_id]
            skip,length=struct.unpack('>HH',self.data[pos+10:pos+14])
            payload=self.data[pos+14:pos+14+length]
            cursor=0 if first else skip-1
            first=False
            while cursor<length:
                c=payload[cursor]
                if c==0x01 and cursor+8<=length and payload[cursor+1:cursor+3]==b'\xff\x05':
                    plen=5; ps=cursor+3; pe=ps+plen
                    expected=int.from_bytes(payload[ps:pe],'big')
                    self.stats['length_check']+=1
                    if current_bytes is not None:
                        joined=b''.join(current_bytes) if isinstance(current_bytes,list) else current_bytes
                        if len(joined)!=expected: raise ValueError(f'length check mismatch {len(joined)} != {expected}')
                        current_bytes=joined
                    elif len(current)==1 and b'\x01' in current:
                        v=current[b'\x01']
                        if len(v)!=expected: raise ValueError('length check dict mismatch')
                        current_bytes=v; current.clear()
                    elif len(current)==2 and b'\x01' in current:
                        v=current[b'\x01']
                        if len(v)!=expected: raise ValueError('length check dict2 mismatch')
                        current_bytes=v
                    cursor=pe; continue
                if 0x01 <= c <= 0x3F:
                    klen=c; key=payload[cursor+1:cursor+1+klen]
                    ps=cursor+2+klen; pe=ps+payload[ps-1]; val=payload[ps:pe]
                    self.stats['kv_long']+=1
                    if current_bytes is None: current[key]=val
                    else:
                        counter=decode_vli(key)
                        if not isinstance(current_bytes,list): current_bytes=[current_bytes]
                        if len(current_bytes)!=counter-1: raise ValueError('partial counter long mismatch')
                        current_bytes.append(val)
                    cursor=pe; continue
                if 0x40 <= c <= 0x7F:
                    key=bytes([c & 0x3F]); ps=cursor+2; pe=ps+payload[cursor+1]; val=payload[ps:pe]
                    self.stats['kv_simple']+=1
                    if current_bytes is None: current[key]=val
                    else:
                        counter=c-0x40
                        if not isinstance(current_bytes,list): current_bytes=[current_bytes]
                        if len(current_bytes)!=counter-1: raise ValueError('partial counter simple mismatch')
                        current_bytes.append(val)
                    cursor=pe; continue
                if 0x81 <= c <= 0xBF:
                    ps=cursor+1; pe=ps+(c-0x80); current[payload[ps:pe]]=None
                    self.stats['set_value']+=1; cursor=pe; continue
                if c==0xC0:
                    self.stats['pop']+=1
                    if not stack: cursor+=1; continue
                    child=current if current else current_bytes
                    parent=stack.pop(); child_key=path.pop(); parent[child_key]=child
                    current=parent; current_bytes=None; cursor+=1; continue
                if 0xC1 <= c < 0xFE:
                    ps=cursor+1; pe=ps+(c-0xC0); key=payload[ps:pe]
                    self.stats['push']+=1
                    if current_bytes is not None: current=OrderedDict([(b'\x01',current_bytes)])
                    stack.append(current); current=OrderedDict(); current_bytes=None; path.append(key); cursor=pe; continue
                if c==0xFF:
                    c2=payload[cursor+1]
                    if 0x01 <= c2 <= 0x04:
                        key=payload[cursor+2:cursor+2+c2]; counter=decode_vli(key); norm_key=key
                        ps=cursor+4+c2; plen=int.from_bytes(payload[cursor+2+c2:cursor+4+c2],'big'); pe=ps+plen
                    elif 0x40 <= c2 < 0x80:
                        counter=decode_vli(bytes([c2]),True); norm_key=bytes([c2 & 0x3F])
                        ps=cursor+4; plen=int.from_bytes(payload[cursor+2:cursor+4],'big'); pe=ps+plen
                    else: raise ValueError(f'unhandled FF {payload[cursor:cursor+20].hex()}')
                    val=payload[ps:pe]
                    if current_bytes is not None:
                        if not isinstance(current_bytes,list): current_bytes=[current_bytes]
                        current_bytes.append(val); self.stats['segment']+=1
                    elif not current and counter==1:
                        current_bytes=[val]; self.stats['segment']+=1
                    else:
                        current[norm_key]=val; self.stats['kv_long_value']+=1
                    cursor=pe; continue
                if c==0x00:
                    ps=cursor+2; pe=ps+payload[cursor+1]
                    if current_bytes is None: current[b'\x00']=payload[ps:pe]
                    self.stats['zero']+=1; cursor=pe; continue
                raise ValueError(f'unhandled token 0x{c:02x} block {bi} cursor {cursor}/{length}')
            if cursor!=length: raise ValueError('block incomplete')
        self.root=root
        return root
