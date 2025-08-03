import asyncio, telnetlib3, logging
import functools
import time
from typing import Callable, Any

logging.basicConfig(level=logging.INFO)

# Make sure it matches your GNS3 ports
ROUTER_PORTS = {
    "R1": 5003,
    "R2": 5004,
    "R3": 5005,
    "R4": 5006,
}

ROUTERS = {
    "R1": {
        "interfaces": {
            "g0/0": ["10.0.12.1", "255.255.255.252"],
            "g2/0": ["10.0.13.1", "255.255.255.252"],
            "e1/0": ["172.16.1.14", "255.255.255.240"],
        }
    },
    "R2": {
        "interfaces": {
            "g0/0": ["10.0.12.2", "255.255.255.252"],
            "g2/0": ["10.0.24.1", "255.255.255.252"],
            "e1/0": ["192.168.2.254", "255.255.255.0"],
        }
    },
    "R3": {
        "interfaces": {
            "g0/0": ["10.0.13.2", "255.255.255.252"],
            "g2/0": ["192.168.3.126", "255.255.255.128"],
            "e1/0": ["10.0.34.1", "255.255.255.252"],
        }
    },
    "R4": {
        "interfaces": {
            "g0/0": ["10.0.24.2", "255.255.255.252"],
            "g2/0": ["192.168.4.254", "255.255.255.0"],
            "e1/0": ["10.0.34.2", "255.255.255.252"],
        }
    },
}

# Make sure it matches your GNS3 ports
PC_PORTS = {
    "PC1": 5007,
    "PC2": 5008,
    "PC3": 5009,
    "PC4": 5010,
}

PCS = {
    "PC1": {
        "interfaces": {
            "eth0": ["172.16.1.1", "/28"],
        },
        "default_route": ROUTERS["R1"]["interfaces"]["e1/0"][0],
    },
    "PC2": {
        "interfaces": {
            "eth0": ["192.168.2.1", "/24"],
        },
        "default_route": ROUTERS["R2"]["interfaces"]["e1/0"][0],
    },
    "PC3": {
        "interfaces": {
            "eth0": ["192.168.3.1", "/25"],
        },
        "default_route": ROUTERS["R3"]["interfaces"]["g2/0"][0],
    },
    "PC4": {
        "interfaces": {
            "eth0": ["192.168.4.1", "/24"],
        },
        "default_route": ROUTERS["R4"]["interfaces"]["g2/0"][0],
    },
}


def async_timed():
    def wrapper(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapped(*args: Any, **kwargs: Any) -> Any:
            print(f"Running {func} with {args}, {kwargs}")
            start = time.time()
            try:
                return await func(*args, **kwargs)
            finally:
                end = time.time()
                total = end - start
                print(f"{func} took {total:.4f} seconds")

        return wrapped

    return wrapper


async def set_interface_ip(
    writer,
    interface: str,
    ip: str,
    mask: str,
) -> None:
    writer.write(f"interface {interface}\r\n")
    writer.write(f"ip address {ip} {mask}\r\n")
    writer.write("no shutdown\r\n")
    writer.write("exit\r\n")
    logging.info(f"Configured {interface} with {ip} {mask}")


async def configure_router(
    reader,
    writer,
    router_name: str,
) -> None:
    if router_name not in ROUTERS:
        raise ValueError(f"Unknown router: {router_name}")
    writer.write("\r\n")
    writer.write("enable\r\n")
    writer.write("conf t\r\n")
    for interface, (ip, mask) in ROUTERS[router_name]["interfaces"].items():
        await set_interface_ip(writer, interface, ip, mask)
    writer.write("end\r\n")
    logging.warning(f"Finished configuration on {router_name}")


async def configure_host(
    reader,
    writer,
    pc_name: str,
) -> None:
    if pc_name not in PCS:
        raise ValueError(f"Unknown PC: {pc_name}")
    ip, mask = PCS[pc_name]["interfaces"]["eth0"]
    default_route = PCS[pc_name]["default_route"]
    writer.write("\r\n")
    writer.write(f"ip address add {ip}{mask} dev eth0\r\n")
    writer.write("\r\n")
    logging.info(f"Configured {pc_name} with IP: {ip} MASK: {mask}")
    writer.write(f"ip route add default via {default_route}\r\n")
    writer.write("\r\n")
    logging.info(f"Configured {pc_name} with default route: {default_route}")


async def open_connection(
    router_name: str,
    host: str,
    port: int,
) -> None:
    reader, writer = await telnetlib3.open_connection(
        host=host,
        port=port,
    )
    logging.info(f"Connected to {writer.get_extra_info('peername')}")
    await configure_router(
        reader,
        writer,
        router_name,
    )
    await writer.drain()


async def open_host_connection(
    pc_name: str,
    host: str,
    port: int,
) -> None:
    reader, writer = await telnetlib3.open_connection(
        host=host,
        port=port,
    )
    logging.info(f"Connected to {writer.get_extra_info('peername')}")
    await configure_host(reader, writer, pc_name)
    await writer.drain()


@async_timed()
async def main() -> None:
    tasks_routers = [
        asyncio.create_task(
            open_connection(
                router_name=name,
                host="127.0.0.1",
                port=port,
            )
        )
        for name, port in ROUTER_PORTS.items()
    ]
    tasks_pc = [
        asyncio.create_task(
            open_host_connection(
                pc_name=name,
                host="127.0.0.1",
                port=port,
            )
        )
        for name, port in PC_PORTS.items()
    ]
    await asyncio.gather(*tasks_routers)
    await asyncio.gather(*tasks_pc)
    logging.warning("------All done------")


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
