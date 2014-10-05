#/usr/bin/env python
import sys, re, json, logging, argparse
from flask import Flask, render_template
from pkg_resources import parse_version

if sys.version_info <= (3,0):
	from commands import getstatusoutput
	import urllib2 as urllib_request
else:
	# uh is pip even for python3?
	from subprocess import getstatusoutput
	import urllib.request as urllib_request

def get_installed(local=False):
	pkgs = []
	if args.pip3:
		command = "pip3 freeze"
	else:
		command = "pip freeze"
	if local:
		command += " --local"
	logging.info("Running "+command)
	code, output = getstatusoutput(command)
	if not code:
		for line in output.split("\n"):
			if line and not line.startswith("##"):
				if line.startswith("-e"):
					name = line.split("#egg=", 1)[1]
					if name.endswith("-dev"):
						name = name[:-4]
					pkgs.append([name, "dev", True])
				else:
					name, version = line.split("==")
					pkgs.append([name, version, False])
	else:
		logging.info(command+" failed with error code "+str(code)+".")
	return pkgs

def get_latest(installed):
	latest = []
	failed = []
	for name, version, editable in installed:
		logging.info("Fetching https://pypi.python.org/pypi/"+name+"/json/.")
		req = urllib_request.Request("https://pypi.python.org/pypi/"+name+"/json/")
		try:
			handler = urllib_request.urlopen(req)
		except urllib_request.HTTPError:
			logging.error("Fetching https://pypi.python.org/pypi/"+name+"/json/ failed.")
			failed.append(name)
			continue
		if handler.getcode() == 200:
			rawJSON = handler.read()
			pkg_info = json.loads(rawJSON.decode('utf-8'))
			if parse_version(version) < parse_version(pkg_info['info']['version']):
				latest.append([name, version, pkg_info['info']['version'], editable])
	# do something about failed ones...
	return latest

app = Flask(__name__)

# index
@app.route('/')
def index():
    return render_template('index.html')

# refresh installed packages/latest versions
@app.route('/refresh', methods=['GET'])
def refresh():
    installed = get_installed()
    return json.dumps({'updates': get_latest(installed), 'installed': installed})

# update all packages, assumes you already checked that this was dangerous...
@app.route('/update', methods=['POST'])
def updateall():
	all_pkgs = json.loads(refresh())
	errors = []
	passes = []
	for u in all_pkgs['updates']:
		logging.info("Attempting to update package "+u[0]+".")
		if args.pip3:
			retcode, output = getstatusoutput("pip3 install "+u[0]+"=="+u[2])
		else:
			retcode, output = getstatusoutput("pip install "+u[0]+"=="+u[2])
		if retcode:
			logging.error("Failed to install "+u[0]+", `pip install "+u[0]+"=="+u[2]+"` returned error code "+str(retcode)+".")
			errors.append({'name': u[0], 'error': output, 'code': retcode})
		else:
			passes.append({'name': u[0], 'version': u[2]})
	return json.dumps({'passes': passes, 'errors': errors})

# update single package
@app.route('/update/<pkg_name>', methods=['POST'])
def update(pkg_name):
	logging.info("Attempting to update package "+pkg_name+".")
	if args.pip3:
		retcode, output = getstatusoutput("pip3 install "+pkg_name)
	else:
		retcode, output = getstatusoutput("pip install "+pkg_name)
	if retcode:
		logging.error("Failed to install "+pkg_name.split("==")[0]+", `pip install "+pkg_name+"` returned error code "+str(retcode)+".")
		return json.dumps({'error': output, 'code': retcode})
	else:
		return ""

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Web App to display updates for installed pip packages on your system.")
    parser.add_argument("-l", help="Log to specified file.")
    parser.add_argument("-H", help="Specify host to serve on (be careful...), defaults to 127.0.0.1.")
    parser.add_argument("-P", help="Specify port to server on, defaults to 5000.")
    parser.add_argument("--pip3", action="store_true", help="Use pip3, default is pip.")
    args = parser.parse_args()
    if args.l:
        logging.basicConfig(filename=args.l, level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    host = args.H or '127.0.0.1'
    port = int(args.P) if args.P else 5000
    app.run(host=host, port=port)
