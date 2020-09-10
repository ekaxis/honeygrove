
from honeygrove.geoip import geoip
from honeygrove.config import Config

from datetime import datetime
from hashlib import sha256
import json
import pprint
from socket import getfqdn

if Config.general.use_broker:
    from honeygrove.broker import BrokerEndpoint
if Config.general.use_geoip:
    from geoip2.errors import AddressNotFoundError
    import geoip2.database

ECS_SERVICE = {'id': sha256(str(Config.general.id).encode('utf-8')).hexdigest(),
               'name': str(Config.general.id).lower(),
               'type': 'honeygrove',
               'version': '0.5.5'
               }

if Config.general.use_geoip:
    try:
        GEO_READER = geoip2.database.Reader(str(Config.folder.geo_ip))
    except FileNotFoundError:
        print("\nGeoIP database file not found: {}\n".format(str(Config.folder.geo_ip)))
        print("\nDisabling GeoIP support!\n")
        Config.general.use_geoip = False

PLACEHOLDER_STRING = '--'

pp = pprint.PrettyPrinter(indent=2, width=41, compact=False, sort_dicts=True)


def _log_json(json_data):
    if Config.jsonlog.use_jsonlog:
        wjson = json_data
        if isinstance(wjson, dict):
            wjson = json.dumps(wjson)
        write_json(wjson + '\n')
    if Config.jsonlog.print_jsonlog:
        pp.pprint(json_data)


def _log_status(message):
    if Config.logging.log_status:
        write(message + '\n')
    if Config.logging.print_status:
        print(message)


def _log_alert(message):
    if Config.logging.log_alerts:
        write(message + '\n')
    if Config.logging.print_alerts:
        print(message)


def write_json(json_data):
    if isinstance(json_data, dict):
        json_data = json.dumps(json_data)
    with open(str(Config.jsonlog.log), 'a+') as fp:
        fp.write(json_data)


def write(message):
    """
    Simplify writing to logfile
    :param message: the message to be written
    """

    with open(str(Config.folder.log), 'a') as fp:
        fp.write(message)


def get_reverse_hostname(ip: str):
    name = getfqdn(ip)
    return name if name != ip else None


def get_ecs_address_dict(ip: str, port: int = None):
    ecs_addr = {'address': ip, 'ip': ip}
    host = get_reverse_hostname(ip)
    if host:
        ecs_addr['domain'] = host
    if port:
        ecs_addr['port'] = port
    return ecs_addr


def get_coordinates(ip: str):
    """
    Gets the Location Information for given IP Address
    from Location Database. Returns False if location
    lookup is disabled

    :param ip: the address out of a log entry
    """

    if Config.general.use_geoip:
        try:
            resp = GEO_READER.city(ip)
        except AddressNotFoundError:
            return None

        lat = float(resp.location.latitude)
        lon = float(resp.location.longitude)
        return [lat, lon]
    else:
        return None


def get_geolocation(ip: str):

    if Config.geoip.use_geoip:
        try:
            addr = geoip(ip)
            if addr.get('message'):
                # checks if it is a private IP
                # to avoid unnecessary treatments and data 
                # formatting in subsequent functions, None will be returned
                return None
            return addr
        except Exception as err:
            pass
    return None



def get_time():
    if Config.general.use_utc:
        return datetime.utcnow()
    else:
        return datetime.now()


def format_time(intime):
    return intime.isoformat()


def info(message: str):
    """
    Log function for administrative messages

    :param message: the message text
    """

    timestamp = format_time(get_time())
    message = '{} [INFO] {}'.format(timestamp, message)
    _log_status(message)


def err(message: str):
    """
    Log function for exceptions

    :param message: the exception message
    """

    timestamp = format_time(get_time())
    message = '{} [ERROR] {}'.format(timestamp, message)
    _log_status(message)


def defer_login(result, *args):
    """
    Wraps log.login for use with deferreds

    :param result: whatever
    :param args: arguments for login
    """

    login(*args)
    return result


def login(service: str, ip: str, port: int, successful: bool, user: str, secret: str = None, valid_for=None):
    """
    Log function to be called when someone attempts to login

    :param service: the concerning service
    :param ip: attacker's IP-Address
    :param port: attackers port
    :param successful: if the attempt was successful
    :param user: the username of the attempt
    :param secret: the password or key of the attempt
    :param valid_for: the services where the login would have actually been valid (used for tracking honeytoken usage)
    """

    timestamp = format_time(get_time())
    coordinates = get_coordinates(ip)

    if not secret:
        secret = PLACEHOLDER_STRING
    if not valid_for:
        secret = PLACEHOLDER_STRING

    ecs_event = {'category': 'alert', 'action': 'login'}
    ecs_hg_login = {'service': service, 'username': user, 'password': secret, 'successful': successful}
    ecs_hg = {'login': ecs_hg_login}

    values = {'@timestamp': timestamp,
              'service': ECS_SERVICE,
              'event': ecs_event,
              # XXX: we don't know the source port currently..
              'source': get_ecs_address_dict(ip),
              'destination': get_ecs_address_dict(Config.general.address, port),
              'honeygrove': ecs_hg}

    addr = get_geolocation(ip)
    addr = addr if addr is not None else {}

    values['source']['addr'] = addr

    if not coordinates and addr:
        coordinates = (addr['lat'], addr['lon'])

    # Append geo coordinates of source, if available
    if coordinates:
        values['source']['geo'] = {'location': '{:.4f},{:.4f}'.format(coordinates[0], coordinates[1])}

    if Config.general.use_broker:
        BrokerEndpoint.BrokerEndpoint.sendLogs(json.dumps(values))

    lat = PLACEHOLDER_STRING
    lon = PLACEHOLDER_STRING
    if coordinates:
        lat = '{:.4f}'.format(coordinates[0])
        lon = '{:.4f}'.format(coordinates[1])

    message = ('{} [LOGIN] {}, {}:{}, Lat: {}, Lon: {}, {}, {}, {}, {}'
               '').format(timestamp, service, ip, port, lat, lon, successful, user, secret, valid_for)

    _log_alert(message)
    _log_json(values)


def request(service: str, remote_ip: str, remote_port: int, local_ip: str, local_port: int, req: str, user: str = None, request_type: str = None):
    """
    Log function to be called when a request is received

    :param service: the concerning service
    :param remote_ip: attacker's IP-Address
    :param remote_port: attackers port
    :param local_ip: local IP that was accessed
    :param local_port: local port that was accessed
    :param req: the received request
    :param user: the user whose session invoked the alert
    :param request_type: for HTTP if the request is a GET or a POST request
    """

    timestamp = format_time(get_time())
    coordinates = get_coordinates(remote_ip)

    ecs_event = {'category': 'warning', 'action': 'request'}
    ecs_hg_request = {'service': service, 'original': req}
    if user:
        ecs_hg_request['user'] = user
    if request_type:
        ecs_hg_request['type'] = request_type

    ecs_hg = {'request': ecs_hg_request}

    values = {'@timestamp': timestamp,
              'service': ECS_SERVICE,
              'event': ecs_event,
              'source': get_ecs_address_dict(remote_ip, remote_port),
              'destination': get_ecs_address_dict(local_ip, local_port),
              'honeygrove': ecs_hg}

    addr = get_geolocation(remote_ip)
    addr = addr if addr is not None else {}

    values['source']['addr'] = addr

    if not coordinates and addr:
        coordinates = (addr['lat'], addr['lon'])

    # Append geo coordinates of source, if available
    if coordinates:
        values['source']['geo'] = {'location': '{:.4f},{:.4f}'.format(coordinates[0], coordinates[1])}

    if Config.general.use_broker:
        BrokerEndpoint.BrokerEndpoint.sendLogs(json.dumps(values))

    lat = PLACEHOLDER_STRING
    lon = PLACEHOLDER_STRING
    if coordinates:
        lat = '{:.4f}'.format(coordinates[0])
        lon = '{:.4f}'.format(coordinates[1])

    message = ('{} [REQUEST] {}, {}:{}->{}:{}, Lat: {}, Lon: {}, {}, {}, {}'
               '').format(timestamp, service, remote_ip, remote_port, local_ip, local_port, lat, lon, req, user, request_type)
    _log_alert(message)
    _log_json(values)


def response(service: str, remote_ip: str, remote_port: int, local_ip: str, local_port: int, resp: str, user: str = None, status_code=None):
    """
    Log function to be called when sending a response

    :param service: the concerning service
    :param remote_ip: attacker's IP-Address
    :param remote_port: attackers port
    :param local_ip: local IP that was accessed
    :param local_port: local port that was accessed
    :param resp: the response sent
    :param user: the user whose session invoked the alert
    :param status_code: the status code sent
    """

    timestamp = format_time(get_time())
    coordinates = get_coordinates(remote_ip)

    ecs_event = {'category': 'warning', 'action': 'response'}
    ecs_hg_request = {'service': service, 'original': resp}
    if user:
        ecs_hg_request['user'] = user
    if status_code:
        ecs_hg_request['status'] = status_code

    ecs_hg = {'response': ecs_hg_request}

    values = {'@timestamp': timestamp,
              'service': ECS_SERVICE,
              'event': ecs_event,
              'source': get_ecs_address_dict(local_ip, local_port),
              'destination': get_ecs_address_dict(remote_ip, remote_port),
              'honeygrove': ecs_hg}
    
    addr = get_geolocation(remote_ip)
    addr = addr if addr is not None else {}

    values['source']['addr'] = addr

    if not coordinates and addr:
        coordinates = (addr['lat'], addr['lon'])

    # Append geo coordinates of source, if available
    if coordinates:
        values['destination']['geo'] = {'location': '{:.4f},{:.4f}'.format(coordinates[0], coordinates[1])}

    if Config.general.use_broker:
        BrokerEndpoint.BrokerEndpoint.sendLogs(json.dumps(values))

    lat = PLACEHOLDER_STRING
    lon = PLACEHOLDER_STRING
    if coordinates:
        lat = '{:.4f}'.format(coordinates[0])
        lon = '{:.4f}'.format(coordinates[1])

    message = ('{} [RESPONSE] {}, {}:{}->{}:{}, Lat: {}, Lon: {}, {}, {}, {}'
               '').format(timestamp, service, local_ip, local_port, remote_ip, remote_port, lat, lon, resp, user, status_code)

    _log_alert(message)
    _log_json(values)


def file(service: str, ip: str, file_name: str, file_path: str = None, user: str = None):
    """
    Log function to be called when receiving a file

    :param service: the concerning service
    :param ip: attacker's IP-Address
    :param file_name: name of the received file
    :param file_path: the path where the file was saved
    :param user: the user whose session invoked the alert
    """

    timestamp = format_time(get_time())
    coordinates = get_coordinates(ip)

    ecs_event = {'category': 'alert', 'action': 'file-upload'}
    ecs_hg_file = {'service': service, 'name': file_name}
    if file_path:
        ecs_hg_file['path'] = file_path
    if user:
        ecs_hg_file['user'] = user

    ecs_hg = {'file-upload': ecs_hg_file}

    values = {'@timestamp': timestamp,
              'service': ECS_SERVICE,
              'event': ecs_event,
              # XXX: we don't know the source port currently..
              'source': get_ecs_address_dict(ip),
              'destination': get_ecs_address_dict(Config.general.address),
              'honeygrove': ecs_hg}
            
    addr = get_geolocation(ip)
    addr = addr if addr is not None else {}

    values['source']['addr'] = addr

    if not coordinates and addr:
        coordinates = (addr['lat'], addr['lon'])

    # Append geo coordinates of source, if available
    if coordinates:
        values['source']['geo'] = {'location': '{:.4f},{:.4f}'.format(coordinates[0], coordinates[1])}

    if Config.general.use_broker:
        BrokerEndpoint.BrokerEndpoint.sendLogs(json.dumps(values))
        if file_path:
            BrokerEndpoint.BrokerEndpoint.sendFile(file_path)

    lat = PLACEHOLDER_STRING
    lon = PLACEHOLDER_STRING
    if coordinates:
        lat = '{:.4f}'.format(coordinates[0])
        lon = '{:.4f}'.format(coordinates[1])

    message = ('{} [FILE] {}, {}, Lat: {}, Lon: {}, {}, {}'
               '').format(timestamp, service, ip, lat, lon, file_name, user)

    _log_alert(message)
    _log_json(values)


def scan(ip, port, time, scan_type):
    """
    Log function to be called when a scan is detected

    :param ip: attacker's IP
    :param port: attacked port
    :param time: timestamp of the scan
    :param scan_type: type of the scan
    """

    timestamp = format_time(time)
    coordinates = get_coordinates(ip)

    ecs_event = {'category': 'warning', 'action': 'scan'}
    ecs_hg_scan = {'port': port, 'type': scan_type}
    ecs_hg = {'scan': ecs_hg_scan}

    values = {'@timestamp': timestamp,
              'service': ECS_SERVICE,
              'event': ecs_event,
              # XXX: we don't know the source port currently..
              'source': get_ecs_address_dict(ip),
              'destination': get_ecs_address_dict(Config.general.address, port),
              'honeygrove': ecs_hg}
    
    addr = get_geolocation(ip)
    addr = addr if addr is not None else {}

    values['source']['addr'] = addr

    if not coordinates and addr:
        coordinates = (addr['lat'], addr['lon'])

    # Append geo coordinates of source, if available
    if coordinates:
        values['source']['geo'] = {'location': '{:.4f},{:.4f}'.format(coordinates[0], coordinates[1])}

    if Config.general.use_broker:
        BrokerEndpoint.BrokerEndpoint.sendLogs(json.dumps(values))

    lat = PLACEHOLDER_STRING
    lon = PLACEHOLDER_STRING
    if coordinates:
        lat = '{:.4f}'.format(coordinates[0])
        lon = '{:.4f}'.format(coordinates[1])

    message = ('{} [{}-SCAN] {}:{}, Lat: {}, Lon: {}'
               '').format(timestamp, scan_type, ip, port, lat, lon)

    _log_alert(message)
    _log_json(values)


def limit_reached(service: str, ip: str):
    """
    Log function to be called when the maximum of connections per host for a service is reached

    :param service: the concerning service
    :param ip: attacker's IP-Address
    """

    timestamp = format_time(get_time())
    coordinates = get_coordinates(ip)

    ecs_event = {'category': 'warning', 'action': 'rate-limited'}
    ecs_hg_limit = {'service': service, 'ip': ip}
    ecs_hg = {'rate-limited': ecs_hg_limit}

    values = {'@timestamp': timestamp,
              'service': ECS_SERVICE,
              'event': ecs_event,
              # XXX: we don't know the source port currently..
              'source': get_ecs_address_dict(ip),
              'destination': get_ecs_address_dict(Config.general.address),
              'honeygrove': ecs_hg}
    
    addr = get_geolocation(ip)
    addr = addr if addr is not None else {}

    values['source']['addr'] = addr

    if not coordinates and addr:
        coordinates = (addr['lat'], addr['lon'])

    # Append geo coordinates of source, if available
    if coordinates:
        values['source']['geo'] = {'location': '{:.4f},{:.4f}'.format(coordinates[0], coordinates[1])}

    if Config.general.use_broker:
        BrokerEndpoint.BrokerEndpoint.sendLogs(json.dumps(values))

    lat = PLACEHOLDER_STRING
    lon = PLACEHOLDER_STRING
    if coordinates:
        lat = '{:.4f}'.format(coordinates[0])
        lon = '{:.4f}'.format(coordinates[1])

    message = '{} [LIMIT REACHED] {}, {}, Lat: {}, Lon: {}'.format(timestamp, service, ip, lat, lon)
    _log_alert(message)
    _log_json(values)


def heartbeat():
    """
    Log function to be called when sending a heartbeat
    """

    timestamp = format_time(get_time())

    if Config.general.use_broker:
        ecs_event = {'category': 'info', 'action': 'heartbeat'}
        values = {'@timestamp': timestamp,
                  'service': ECS_SERVICE,
                  'event': ecs_event}
        BrokerEndpoint.BrokerEndpoint.sendLogs(values)

    message = ('{} [Heartbeat]'.format(timestamp))
    _log_status(message)
    _log_json(values)
