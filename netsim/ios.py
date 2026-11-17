from __future__ import annotations

from ipaddress import IPv4Address, IPv4Interface, IPv4Network
from typing import Optional

from .model import LabError, NetworkLab


def _ios_acl_operand(parts: list[str], index: int) -> tuple[str, int]:
    if index >= len(parts): raise LabError("missing ACL address")
    token=parts[index].lower()
    if token == "any": return "any", index+1
    if token == "host":
        if index+1 >= len(parts): raise LabError("missing host address")
        IPv4Address(parts[index+1]); return f"{parts[index+1]}/32", index+2
    if "/" in parts[index]:return str(IPv4Network(parts[index],strict=False)),index+1
    IPv4Address(parts[index])
    if index+1 >= len(parts): return f"{parts[index]}/32", index+1
    try:
        wc=IPv4Address(parts[index+1])
    except ValueError:
        return f"{parts[index]}/32", index+1
    mask_int=0xFFFFFFFF ^ int(wc); mask=str(IPv4Address(mask_int))
    return str(IPv4Network(f"{parts[index]}/{mask}", strict=False)), index+2


class IOSSession:
    """Small, stateful IOS-like command surface backed by NetworkLab.

    It intentionally models the CCNA command workflow rather than attempting to
    emulate a vendor IOS binary. Commands mutate the same state as the agent API.
    """

    def __init__(self, lab: NetworkLab, device: str):
        self.lab = lab
        self.device = device
        self.mode = "user"
        self.interface: Optional[str] = None
        self.ospf_process: Optional[int] = None
        self.pending_dot1q: dict[str, int] = {}
        self.awaiting_enable=False
        self.context={}

    @property
    def prompt(self) -> str:
        d=self.lab._device(self.device)
        if d.config.get("boot_state")=="rommon":return "rommon>"
        name = d.config.get("hostname",self.device)
        return {
            "user": f"{name}>", "priv": f"{name}#", "config": f"{name}(config)#",
            "interface": f"{name}(config-if)#", "router-ospf": f"{name}(config-router)#", "router-rip": f"{name}(config-router)#", "router-eigrp": f"{name}(config-router)#", "acl":f"{name}(config-ext-nacl)#", "dhcp":f"{name}(dhcp-config)#",
        }.get(self.mode, f"{name}#")

    def execute(self, line: str) -> str:
        line = line.strip()
        if not line:
            return self.prompt
        low = " ".join(line.lower().split())
        from copy import deepcopy
        before=deepcopy(self.lab.__dict__)
        session_before=(self.mode,self.interface,deepcopy(self.context),deepcopy(self.pending_dot1q),self.awaiting_enable)
        try:
            output = self._execute(line, low)
            return (output + "\n" if output else "") + self.prompt
        except (LabError, ValueError, KeyError, IndexError) as e:
            self.lab.__dict__.clear();self.lab.__dict__.update(before)
            self.mode,self.interface,self.context,self.pending_dot1q,self.awaiting_enable=session_before
            if self.awaiting_enable:self.awaiting_enable=False
            return f"% {e}\n{self.prompt}"

    def _execute(self, line: str, low: str) -> str:
        d = self.lab._device(self.device)
        if not d.powered:raise LabError("Device is powered off")
        from .device_config import settings,action as configure
        c=settings(d)
        if self.awaiting_enable:
            self.awaiting_enable=False
            if line!=c.get("enable_secret"):raise LabError("Authentication failed")
            self.mode="priv";return ""
        if c['boot_state']=='rommon':
            if low in ('?','help'):return 'boot [FILE], confreg [VALUE], dir [flash:], reset, set [NAME VALUE], unset NAME, tftpdnld'
            if low=='set':return '\n'.join(k+'='+v for k,v in sorted(c.get('rommon_environment',{}).items()))
            if low.startswith('unset '):c.setdefault('rommon_environment',{}).pop(line.split()[1],None);d.config=c;return ''
            if low=='confreg':return c.get('config_register','0x2102')
            if low.startswith('boot '):
                configure(self.lab,{'action':'boot_image','device':self.device,'file':line.split()[1].removeprefix('flash:')});configure(self.lab,{'action':'boot','device':self.device});return 'Boot attempted'
            if low=='tftpdnld':
                from .device_services import transfer
                env=c.get('rommon_environment',{});port=next(p.name for p in d.interfaces.values() if p.media in ('copper','fiber-mm','fiber-sm'))
                for key in ('IP_ADDRESS','IP_SUBNET_MASK','TFTP_SERVER','TFTP_FILE'):
                    if key not in env:raise LabError('missing ROMMON variable '+key)
                self.lab.set_ip(self.device,port,str(IPv4Interface(env['IP_ADDRESS']+'/'+env['IP_SUBNET_MASK'])))
                if env.get('DEFAULT_GATEWAY'):self.lab.add_static_route(self.device,'0.0.0.0/0',next_hop=env['DEFAULT_GATEWAY'])
                transfer(self.lab,{'device':self.device,'server':env['TFTP_SERVER'],'protocol':'tftp','operation':'get','file':env['TFTP_FILE']});return 'TFTP image downloaded'
            if low in ('dir','dir flash:'):return '\n'.join(c['files'])
            if low in ('boot','reset'):configure(self.lab,{'action':'boot','device':self.device});return 'Boot attempted'
            if low.startswith('confreg '):c['config_register']=line.split()[-1];d.config=c;return 'Configuration register set'
            if low.startswith('set '):
                parts=line.split(None,2)
                if len(parts)!=3:raise LabError('set NAME VALUE')
                c.setdefault('rommon_environment',{})[parts[1]]=parts[2];d.config=c;return ''
            raise LabError('ROMMON: use dir, set, confreg or boot; select a valid simulated IOS image')
        if self.mode=='user' and (low in ('reload','write memory','wr','write','erase startup-config','write erase') or low.startswith(('copy ','delete '))):raise LabError('privileged EXEC mode required; use enable')
        from .ios_reference import execute as reference_execute
        if not self.awaiting_enable and c['boot_state']!='rommon':
            output=reference_execute(self,line,low)
            if output is not None:return output
        if low in ('write memory','wr','write','copy running-config startup-config','copy run start'):
            configure(self.lab,{'action':'save_startup','device':self.device});return 'Building configuration...\n[OK]'
        if low in ('erase startup-config','write erase'):
            configure(self.lab,{'action':'erase_startup','device':self.device});return 'Erase of nvram: complete'
        if low=='reload':configure(self.lab,{'action':'boot','device':self.device});self.mode='user';return 'Device reloaded'
        if low in ('dir','dir flash:','show flash:'):return '\n'.join(c['files'])
        if low=='show version':return f"Packet Tracker and Simulator simulated IOS\nModel {d.model or d.kind}\nBoot image {c['boot_image']}\nConfiguration register {c.get('config_register','0x2102')}"
        if low in ('show startup-config','sh start'):
            if c['startup'] is None:return 'startup-config is not present'
            from copy import deepcopy
            from .device_config import restore
            candidate=deepcopy(self.lab);restore(candidate,candidate.devices[self.device],c['startup']);return IOSSession(candidate,self.device)._running_config()
        if low.startswith(('copy ','delete ')):
            parts=line.split()
            if parts[0].lower()=='delete' and len(parts)==2:
                configure(self.lab,{'action':'file_delete','device':self.device,'file':parts[1].removeprefix('flash:')});return 'File deleted'
            if len(parts)==3 and parts[1].lower() in ('running-config','startup-config') and parts[2].startswith('flash:'):
                text=self._running_config() if parts[1].lower()=='running-config' else __import__('json').dumps(c['startup'])
                configure(self.lab,{'action':'file_write','device':self.device,'file':parts[2][6:],'content':text});return 'File copied'
            raise LabError('Use Device Configuration Transfer for simulated FTP/TFTP; supported local copy is running-config flash:<file>')
        if low.startswith('show iox') or low.startswith('iox ') or low.startswith('ioxclient '):
            from .special_devices import iox_command
            return iox_command(self.lab,self.device,line)
        if low.startswith('show license') or low.startswith('license '):
            from .special_devices import license_command
            return license_command(self.lab,self.device,line)
        if low in {"enable", "en"}:
            if self.mode=="user" and c.get("enable_secret"):
                self.awaiting_enable=True;return "Password:"
            self.mode = "priv"; return ""
        if low in {"disable"}:
            self.mode = "user"; return ""
        if low in {"configure terminal", "conf t", "config t"}:
            if self.mode!="priv":raise LabError("privileged EXEC mode required; use enable")
            self.mode = "config"; return "Enter configuration commands, one per line."
        if low == "end":
            if self.mode=='user':raise LabError('end requires configuration or privileged EXEC mode')
            self.mode = "priv"; self.interface = None; return ""
        if low == "exit":
            if self.mode in {"interface", "router-ospf", "router-rip", "router-eigrp", "acl", "dhcp"}: self.mode = "config"
            elif self.mode == "config": self.mode = "priv"
            elif self.mode == "priv": self.mode = "user"
            return ""

        if low.startswith("show ") or low in {"sh ip int br", "sh ip route", "sh run", "sh vlan br"}:
            return self._show(low)
        if self.mode=="config" and low=="ipv6 unicast-routing":configure(self.lab,{"action":"global","device":self.device,"ipv6_routing":True});return ""
        if self.mode=="config" and low.startswith("ipv6 route "):
            parts=line.split();configure(self.lab,{"action":"ipv6_route","device":self.device,"network":parts[2],"next_hop":parts[3]});return ""
        if self.mode=="interface" and low.startswith("ipv6 address "):
            configure(self.lab,{"action":"interface","device":self.device,"interface":self.interface,"ipv6":line.split()[2]});return ""
        if low.startswith("ping "):
            ip = line.split()[1]
            return self.lab.ping(self.device, ip)[1]
        if low.startswith("traceroute ") or low.startswith("trace "):
            ip = line.split()[1]
            return self.lab.traceroute(self.device, ip)[1]

        if self.mode == "config":
            if low.startswith(('enable secret ','enable password ')):configure(self.lab,{'action':'global','device':self.device,'enable_secret':line.split(None,2)[2]});return ''
            if low.startswith('hostname '):configure(self.lab,{'action':'global','device':self.device,'hostname':line.split()[1]});return ''
            if low.startswith('router eigrp '):
                asn=int(line.split()[2]);configure(self.lab,{'action':'eigrp','device':self.device,'asn':asn});self.context={'eigrp_asn':asn};self.mode='router-eigrp';return ''
            if low.startswith('no router eigrp '):configure(self.lab,{'action':'eigrp','device':self.device,'asn':int(line.split()[3]),'delete_process':True});return ''
            if low=='router rip':self.mode='router-rip';return ''
            if low=='ip routing':
                if d.kind!='switch' and not d.config.get('multilayer_switch'):raise LabError('ip routing requires a multilayer switch')
                configure(self.lab,{'action':'svi','device':self.device,'vlan':1});return ''
            if low.startswith('username '):
                parts=line.split();index=next((i for i,v in enumerate(parts) if v in ('password','secret')),None)
                if index is None or index+1>=len(parts):raise LabError('username NAME [privilege N] secret PASSWORD')
                configure(self.lab,{'action':'local_user','device':self.device,'username':parts[1],'password':parts[index+1],'privilege':int(parts[parts.index('privilege')+1]) if 'privilege' in parts else 1});return ''
            if low.startswith('logging '):configure(self.lab,{'action':'logging','device':self.device,'server':line.split()[-1]});return ''
            if low.startswith('ntp server '):configure(self.lab,{'action':'clock_sync','device':self.device,'server':line.split()[2],'protocol':'ntp'});return ''
            if low.startswith('boot system '):configure(self.lab,{'action':'boot_image','device':self.device,'file':line.split()[-1].removeprefix('flash:')});return ''
            if low.startswith('interface ') or low.startswith("int "):
                ifname = line.split(None, 1)[1].strip()
                if ifname.lower().startswith('vlan') and ifname[4:].isdigit() and ifname not in d.interfaces:
                    configure(self.lab,{'action':'svi','device':self.device,'vlan':int(ifname[4:])});d=self.lab.devices[self.device]
                if ifname not in d.interfaces:
                    if d.kind != "router" or "." not in ifname:
                        raise LabError(f"Invalid interface {ifname}")
                    parent = ifname.split(".", 1)[0]
                    self.lab._iface(self.device, parent)
                self.interface = ifname; self.mode = "interface"; return ""
            if low.startswith("vlan "):
                if (d.kind != "switch" and not d.config.get("multilayer_switch",False)): raise LabError("VLAN configuration requires a switch")
                self.lab.add_vlan(self.device, int(line.split()[1])); return ""
            if low.startswith("spanning-tree mode "):
                self.lab.set_stp_mode(self.device, line.split()[-1]); return ""
            if low.startswith("spanning-tree vlan ") and " priority " in low:
                parts = line.split(); self.lab.set_stp_priority(self.device, int(parts[-1])); return ""
            if low.startswith("access-list "):
                parts=line.split()
                if len(parts) < 4: raise LabError("incomplete access-list command")
                name, action = parts[1], parts[2].lower()
                try: num=int(name)
                except ValueError: num=None
                standard = num is not None and (1 <= num <= 99 or 1300 <= num <= 1999)
                if standard:
                    src, _ = _ios_acl_operand(parts,3)
                    self.lab.add_acl_rule(self.device,name,action,"ip",src,"any"); return ""
                protocol=parts[3].lower()
                src, idx = _ios_acl_operand(parts,4)
                from .acl_ports import parse
                source_port,idx=parse(parts,idx)
                dst, idx = _ios_acl_operand(parts,idx)
                destination_port,idx=parse(parts,idx)
                self.lab.add_acl_rule(self.device,name,action,protocol,src,dst,source_port=source_port,destination_port=destination_port); return ""
            if low.startswith("no access-list "):
                self.lab.clear_acl(self.device,line.split()[2]); return ""
            if low.startswith("ip nat inside source static "):
                parts=line.split()
                if len(parts) != 7: raise LabError("usage: ip nat inside source static <inside-local> <inside-global>")
                self.lab.add_nat_static(self.device,parts[5],parts[6]); return ""
            if low.startswith("ip nat inside source list ") and low.endswith(" overload"):
                parts=line.split()
                if len(parts) != 9 or parts[6].lower() != "interface":
                    raise LabError("usage: ip nat inside source list <acl> interface <iface> overload")
                acl_name=parts[5]; outside_if=parts[7]
                rules=d.acls.get(acl_name,[])
                permit=next((r for r in rules if r.action=="permit" and r.protocol=="ip"),None)
                if not permit: raise LabError(f"ACL {acl_name} has no permitted source network")
                self.lab.add_nat_overload(self.device,permit.src,outside_if); return ""
            if low == "no ip nat inside source":
                self.lab.clear_nat(self.device); return ""
            if low.startswith("ip route "):
                parts = line.split()
                if len(parts) < 5: raise LabError("usage: ip route <network> <mask> <next-hop>")
                net = str(IPv4Network(f"{parts[2]}/{parts[3]}", strict=False))
                self.lab.add_static_route(self.device, net, next_hop=parts[4]); return ""
            if low.startswith("router ospf "):
                parts = line.split()
                if len(parts) != 3: raise LabError('usage: router ospf <process-id>')
                self.lab.enable_ospf(self.device, automatic=False, process_id=parts[2])
                self.ospf_process = self.lab._device(self.device).ospf_process_id
                self.mode = "router-ospf"; return ""
            if low == "cdp run": self.lab.set_discovery_protocol(self.device, "cdp", True); return ""
            if low == "no cdp run": self.lab.set_discovery_protocol(self.device, "cdp", False); return ""
            if low == "lldp run": self.lab.set_discovery_protocol(self.device, "lldp", True); return ""
            if low == "no lldp run": self.lab.set_discovery_protocol(self.device, "lldp", False); return ""
            raise LabError("Invalid input detected at '^' marker")

        if self.mode == "router-eigrp":
            parts=line.split();remove=parts[0].lower()=='no'
            if remove:parts=parts[1:]
            if len(parts) not in (2,3) or parts[0].lower()!='network':raise LabError('EIGRP: network ADDRESS [WILDCARD] or no network ADDRESS [WILDCARD]')
            value=parts[1]
            if len(parts)==3:
                mask=str(IPv4Address(0xFFFFFFFF ^ int(IPv4Address(parts[2]))));value=str(IPv4Network(value+'/'+mask,strict=False))
            elif '/' not in value:
                first=int(value.split('.')[0]);value+=('/8' if first<128 else '/16' if first<192 else '/24')
            configure(self.lab,{'action':'eigrp','device':self.device,'asn':self.context['eigrp_asn'],'network':value,'enabled':not remove});return ''

        if self.mode == "router-rip":
            if low.startswith('version '):c['rip_version']=int(line.split()[1]);d.config=c;return ''
            if low.startswith(('network ','no network ')):
                network=line.split()[-1]
                if '/' not in network:
                    first=int(network.split('.')[0]);network+=('/8' if first<128 else '/16' if first<192 else '/24')
                configure(self.lab,{'action':'rip','device':self.device,'network':network,'enabled':not low.startswith('no ')});return ''
            raise LabError('RIP: network, no network or version')
        if self.mode == "router-ospf":
            parts = line.split()
            remove = bool(parts and parts[0].lower() == 'no')
            if remove: parts = parts[1:]
            if len(parts) == 5 and parts[0].lower() == 'network' and parts[3].lower() == 'area':
                ip, wildcard = parts[1], parts[2]
                mask_int = 0xFFFFFFFF ^ int(IPv4Address(wildcard))
                mask = str(IPv4Address(mask_int))
                network = str(IPv4Network(f"{ip}/{mask}", strict=False))
                if remove: self.lab.remove_ospf_network(self.device, network, parts[4])
                else: self.lab.enable_ospf(self.device, network, parts[4])
                return ""
            raise LabError("Invalid router OSPF command")

        if self.mode == "interface":
            ifname = self.interface
            if not ifname: raise LabError("no interface selected")
            if low.startswith(('speed ','duplex ','clock rate ','description ')):
                field='clock_rate' if low.startswith('clock rate ') else low.split()[0]
                value=line.split(None,2)[-1] if field=='clock_rate' else line.split(None,1)[1]
                if field=='description':self.lab._iface(self.device,ifname).description=value
                else:configure(self.lab,{'action':'interface','device':self.device,'interface':ifname,field:int(value) if field=='clock_rate' else value})
                return ''
            if low in {"shutdown", "shut"}:
                if ifname not in d.interfaces: raise LabError("subinterface must be created before shutdown")
                self.lab.set_interface_state(self.device, ifname, False); return ""
            if low in {"no shutdown", "no shut"}:
                if ifname not in d.interfaces: raise LabError("subinterface must be created before no shutdown")
                self.lab.set_interface_state(self.device, ifname, True); return ""
            if low.startswith("encapsulation dot1q "):
                if d.kind != "router" or "." not in ifname: raise LabError("encapsulation dot1Q requires a router subinterface")
                self.pending_dot1q[ifname] = int(line.split()[-1]); return ""
            if low.startswith("ip address "):
                parts = line.split()
                if len(parts) != 4: raise LabError("usage: ip address <address> <mask>")
                cidr = str(IPv4Interface(f"{parts[2]}/{parts[3]}"))
                if ifname in d.interfaces:
                    self.lab.set_ip(self.device, ifname, cidr)
                else:
                    vlan = self.pending_dot1q.get(ifname)
                    if vlan is None: raise LabError("configure encapsulation dot1Q first")
                    self.lab.add_subinterface(self.device, ifname.split('.',1)[0], vlan, cidr)
                self.lab.recompute_ospf(); return ""
            if low == "no ip address":
                self.lab._iface(self.device, ifname).ip = None; self.lab.recompute_ospf(); return ""
            if low == "ip nat inside": self.lab.set_nat_role(self.device,ifname,"inside"); return ""
            if low == "ip nat outside": self.lab.set_nat_role(self.device,ifname,"outside"); return ""
            if low in {"no ip nat inside","no ip nat outside"}: self.lab.set_nat_role(self.device,ifname,None); return ""
            if low.startswith("ip access-group "):
                parts=line.split()
                if len(parts) != 4: raise LabError("usage: ip access-group <acl> <in|out>")
                self.lab.set_access_group(self.device,ifname,parts[2],parts[3]); return ""
            if low.startswith("no ip access-group "):
                parts=line.split()
                if len(parts) < 5: raise LabError("usage: no ip access-group <acl> <in|out>")
                self.lab.set_access_group(self.device,ifname,None,parts[-1]); return ""
            if low.startswith("ip helper-address "):
                self.lab.set_helper_address(self.device, ifname, line.split()[-1]); return ""
            if low == "no ip helper-address":
                self.lab.set_helper_address(self.device, ifname, None); return ""
            if low.startswith("switchport mode "):
                if (d.kind != "switch" and not d.config.get("multilayer_switch",False)): raise LabError("switchport is only valid on switches")
                mode = line.split()[-1].lower(); p = self.lab._iface(self.device, ifname)
                if mode == "access": self.lab.set_switchport_access(self.device, ifname, p.access_vlan)
                elif mode == "trunk": self.lab.set_switchport_trunk(self.device, ifname, p.allowed_vlans)
                else: raise LabError("switchport mode must be access or trunk")
                return ""
            if low.startswith("switchport access vlan "):
                self.lab.set_switchport_access(self.device, ifname, int(line.split()[-1])); return ""
            if low.startswith("switchport trunk allowed vlan "):
                vals = [int(x) for x in line.split()[-1].split(',') if x]
                self.lab.set_switchport_trunk(self.device, ifname, vals); return ""
            if low.startswith("switchport trunk native vlan "):
                self.lab.set_native_vlan(self.device, ifname, int(line.split()[-1])); return ""
            if low == "spanning-tree portfast":
                self.lab.set_portfast(self.device, ifname, True); return ""
            if low == "no spanning-tree portfast":
                self.lab.set_portfast(self.device, ifname, False); return ""
            if low.startswith("channel-group ") and " mode " in low:
                parts = line.split(); self.lab.set_channel_group(self.device, ifname, int(parts[1]), parts[-1]); return ""
            if low.startswith("no channel-group"):
                self.lab.clear_channel_group(self.device, ifname); return ""
            raise LabError("Invalid interface command")

        raise LabError("Command requires privileged/configuration mode or is not implemented")

    def _show(self, low: str) -> str:
        d = self.lab._device(self.device)
        if low in {"show ip interface brief", "sh ip int br", "show ip int brief"}:
            out=["Interface              IP-Address      Status  Protocol"]
            for i in d.interfaces.values():
                ip=str(i.ipv4.ip) if i.ip else "unassigned"
                admin="up" if i.admin_up else "administratively down"
                proto="up" if self.lab._iface_effective_up(self.device,i.name) else "down"
                out.append(f"{i.name:<22} {ip:<15} {admin:<22} {proto}")
            return "\n".join(out)
        if low in {"show ip route", "sh ip route"}:
            codes={"connected":"C","static":"S","default":"S*","ospf":"O","eigrp":"D","rip":"R"};out=["Codes: C - connected, S - static, O - OSPF", ""]
            for r in self.lab.routing_table(self.device):
                via=f" via {r.next_hop}" if r.next_hop else f", {r.interface}"
                out.append(f"{codes.get(r.source,'?'):<2} {r.network:<19}{via}")
            return "\n".join(out)
        if low in {"show vlan brief", "sh vlan br", "show vlan"}:
            if (d.kind!="switch" and not d.config.get("multilayer_switch",False)): raise LabError("VLAN database is only available on switches")
            rows=["VLAN Name                             Status    Ports"]
            for vlan in sorted(d.vlans):
                ports=','.join(i.name for i in d.interfaces.values() if i.mode=="access" and i.access_vlan==vlan)
                rows.append(f"{vlan:<4} VLAN{vlan:<28} active    {ports}")
            return "\n".join(rows)
        if low in {"show mac address-table", "show mac-address-table"}:
            rows=["Vlan    Mac Address       Type        Ports"]
            for key,port in sorted(d.mac_table.items()):
                vlan,mac=key.split(':',1); rows.append(f"{vlan:<7} {mac:<17} DYNAMIC     {port}")
            return "\n".join(rows)
        if low in {"show arp", "show ip arp"}:
            return "\n".join(["Protocol  Address          Hardware Addr"]+[f"Internet  {ip:<16} {mac}" for ip,mac in sorted(d.arp_table.items())])
        if low.startswith("show spanning-tree"):
            parts=low.split(); vlan=1
            if "vlan" in parts:
                vlan=int(parts[parts.index("vlan")+1])
            st=self.lab.spanning_tree(vlan); rows=[f"VLAN{vlan:04d}", f"  Root ID    Bridge {st.get('component_roots', {}).get(self.device, st['root'])}", f"  Bridge ID  Priority {d.stp_priority}", "", "Interface        Role Sts Cost"]
            for key,info in sorted(st['ports'].items()):
                sw,ifn=key.split(':',1)
                if sw==self.device: rows.append(f"{ifn:<16} {info['role'][:4]:<4} {info['state'][:3].upper():<3} {info.get('cost','-')}")
            return "\n".join(rows)
        if low == "show etherchannel summary":
            rows=["Group  Port-channel  Protocol    Ports"]
            for g in self.lab.etherchannel_summary(self.device):
                flag="SU" if g['operational'] else "SD";ports=' '.join(f"{p}(P)" if g['operational'] else f"{p}(s)" for p in g['ports'])
                rows.append(f"{g['group']:<6} {g['name']}({flag})       {g['protocol']:<10} {ports}")
            return "\n".join(rows)
        if low in {"show cdp neighbors", "sh cdp nei"}:
            rows=["Device ID        Local Intrfce     Capability  Platform  Port ID"]
            for n in self.lab.neighbors(self.device,"cdp"): rows.append(f"{n['device']:<16} {n['local_interface']:<16} {n['capability']:<11} {n['platform']:<9} {n['remote_interface']}")
            return "\n".join(rows)
        if low in {"show lldp neighbors", "sh lldp nei"}:
            rows=["Device ID        Local Intf        Hold-time  Capability  Port ID"]
            for n in self.lab.neighbors(self.device,"lldp"): rows.append(f"{n['device']:<16} {n['local_interface']:<16} 120        {n['capability']:<11} {n['remote_interface']}")
            return "\n".join(rows)
        if low in {"show ip nat translations", "sh ip nat trans"}:
            rows=["Pro  Inside global      Inside local       Outside local      Outside global"]
            for local,glob in sorted(d.nat_static.items()): rows.append(f"---  {glob:<18} {local:<18} ---                ---")
            for key,local in sorted(d.nat_sessions.items()):
                glob,remote,proto=key.split('|',2); rows.append(f"{proto:<4} {glob:<18} {local:<18} {remote:<18} {remote}")
            return "\n".join(rows)
        if low in {"show ip nat statistics", "sh ip nat stat"}:
            inside=','.join(i.name for i in d.interfaces.values() if i.nat_role=="inside") or "-"
            outside=','.join(i.name for i in d.interfaces.values() if i.nat_role=="outside") or "-"
            return f"Inside interfaces: {inside}\nOutside interfaces: {outside}\nStatic translations: {len(d.nat_static)}\nDynamic translations: {len(d.nat_sessions)}"
        if low in {"show access-lists", "show ip access-lists", "sh access-lists"}:
            if not d.acls: return "(no access lists)"
            rows=[]
            for name,rules in sorted(d.acls.items()):
                rows.append(f"IP access list {name}")
                for r in rules: rows.append(f"    {r.sequence} {r.action} {r.protocol} {r.src} {r.dst}")
            return "\n".join(rows)
        if low in {"show running-config", "sh run", "show run"}:
            return self._running_config()
        if low in {"show interfaces", "sh interfaces"}:
            rows=[]
            for i in d.interfaces.values():
                proto="up" if self.lab._iface_effective_up(self.device,i.name) else "down"
                rows.append(f"{i.name} is {'up' if i.admin_up else 'administratively down'}, line protocol is {proto}\n  Internet address is {i.ip or 'unassigned'}")
            return "\n".join(rows)
        raise LabError("show command not implemented")

    def _running_config(self) -> str:
        d=self.lab._device(self.device); out=["Building configuration...","","version Packet-Tracker",f"hostname {d.config.get('hostname',d.name)}","!"]
        if d.cdp_enabled: out.append("cdp run")
        if d.lldp_enabled: out.append("lldp run")
        if (d.kind=="switch" or d.config.get("multilayer_switch",False)):
            out.append(f"spanning-tree mode {d.stp_mode}")
            for vlan in sorted(d.vlans): out.append(f"vlan {vlan}")
        for i in d.interfaces.values():
            out.append(f"interface {i.name}")
            if i.encapsulation_vlan is not None: out.append(f" encapsulation dot1Q {i.encapsulation_vlan}")
            if i.ip:
                ipif=i.ipv4; out.append(f" ip address {ipif.ip} {ipif.network.netmask}")
            if i.ipv6:out.append(f" ipv6 address {i.ipv6}")
            if i.description:out.append(f" description {i.description}")
            if i.speed!='auto':out.append(f" speed {i.speed}")
            if i.duplex!='auto':out.append(f" duplex {i.duplex}")
            if i.media=='serial' and i.clock_rate:out.append(f" clock rate {i.clock_rate}")
            if i.mtu!=1500:out.append(f" mtu {i.mtu}")
            if i.helper_address: out.append(f" ip helper-address {i.helper_address}")
            if i.ip_access_group_in: out.append(f" ip access-group {i.ip_access_group_in} in")
            if i.ip_access_group_out: out.append(f" ip access-group {i.ip_access_group_out} out")
            if i.nat_role: out.append(f" ip nat {i.nat_role}")
            if (d.kind=="switch" or d.config.get("multilayer_switch",False)):
                out.append(f" switchport mode {i.mode}")
                if i.mode=="access": out.append(f" switchport access vlan {i.access_vlan}")
                else:
                    out.append(f" switchport trunk native vlan {i.native_vlan}");out.append(f" switchport trunk allowed vlan {','.join(map(str,i.allowed_vlans))}")
                if i.portfast: out.append(" spanning-tree portfast")
                if i.channel_group: out.append(f" channel-group {i.channel_group} mode {i.channel_mode}")
            if not i.admin_up: out.append(" shutdown")
            out.append("!")
        for name,rules in sorted(d.acls.items()):
            for r in rules:
                def predicate(p):
                    return '' if not p else ' '+p['op']+' '+str(p['first'])+(' '+str(p['last']) if p['op']=='range' else '')
                standard=name.isdigit() and (1<=int(name)<=99 or 1300<=int(name)<=1999)
                out.append(f"access-list {name} {r.action} "+(r.src if standard else f"{r.protocol} {r.src}"+predicate(r.source_port)+f" {r.dst}"+predicate(r.destination_port)))
        for local,glob in sorted(d.nat_static.items()): out.append(f"ip nat inside source static {local} {glob}")
        for nr in d.nat_overload: out.append(f"! PAT {nr['network']} interface {nr['outside_iface']} overload")
        for r in d.routes:
            if r.source=="static" and r.next_hop:
                net=IPv4Network(r.network);out.append(f"ip route {net.network_address} {net.netmask} {r.next_hop}")
        if d.config.get('ipv6_routing'):out.append('ipv6 unicast-routing')
        for asn,networks in d.config.get('eigrp',{}).items():
            out.append('router eigrp '+asn)
            for network in networks:out.append(' network '+network)
            out.append('!')
        if d.config.get('rip'):
            out.append('router rip')
            for network in d.config['rip']:out.append(' network '+network)
            out.append('!')
        for name,pool in d.dhcp_pools.items():
            net=IPv4Network(pool.network);out.extend(['ip dhcp pool '+name,f' network {net.network_address} {net.netmask}',' default-router '+pool.gateway])
            if pool.dns:out.append(' dns-server '+pool.dns)
            out.append('!')
        if d.ospf_enabled:
            out.append(f"router ospf {d.ospf_process_id}")
            if d.ospf_auto:
                out.append(" network 0.0.0.0 255.255.255.255 area 0")
            for n in d.ospf_networks:
                net=IPv4Network(n); wc=IPv4Address(0xFFFFFFFF ^ int(net.netmask)); out.append(f" network {net.network_address} {wc} area {d.ospf_areas.get(n, 0)}")
        out.extend(["!","end"]);return "\n".join(out)
