from __future__ import print_function

import os
import tempfile
import shutil

from vsc.utils import fancylogger

from easybuild.framework.easyconfig.easyconfig import ActiveMNS
from easybuild.tools.version import VERSION
from easybuild.tools.build_log import EasyBuildError
from easybuild.tools.filetools import which
from easybuild.tools.run import run_cmd
_log = fancylogger.getLogger('tools.package.docker')  # pylint: disable=C0103


def check_docker_packaging():
    """Check the existence of docker executable"""
    docker_path = which('docker')
    if not docker_path:
        raise EasyBuildError("Selected packaging tool 'docker' not found")

    _log.info("Selected packaging tool 'docker' found at %s", docker_path)


DOCKERFILE_TMPL_UBUNTU1604 = """\
FROM ubuntu:16.04
LABEL maintainer=mohamed.abidi@brightcomputing.com

RUN apt-get update && \\
    apt-get install -y python python-pip lmod curl wget

RUN pip install -U pip setuptools && \\
    pip install easybuild=={easybuild_version}

RUN mkdir /app && \\
    mkdir /scratch && \\
    mkdir /scratch/tmp && \\
    useradd -m -s /bin/bash easybuild && \\
    chown easybuild:easybuild -R /app && \\
    chown easybuild:easybuild -R /scratch

RUN OS_DEPS='{os_deps}' && \\
    for dep in ${{OS_DEPS}}; do apt-get -qq install ${{dep}} || true; done

USER easybuild

RUN set -x &&  \\
    . /usr/share/lmod/lmod/init/sh && \\
    eb {easybuild_filename} --robot --installpath=/app/ --prefix=/scratch --tmpdir=/scratch/tmp

RUN touch ${{HOME}}/.profile && \\
    echo '\\n# Added by easybuild docker packaging' >> ${{HOME}}/.profile && \\
    echo 'source /usr/share/lmod/lmod/init/bash' >> ${{HOME}}/.profile && \\
    echo 'module use {init_modulepaths}' >> ${{HOME}}/.profile && \\
    echo 'module load {modules}' >> ${{HOME}}/.profile
"""


def generate_docker_image(easyconfigs):
    ec = easyconfigs[0]['ec']
    app_name = ec['name']
    app_version = ec['version']
    app_version_suffix = ec['versionsuffix']

    os_deps = ec['osdependencies']  # TODO better parsing

    easybuild_filename = '%s-%s%s.eb' % (app_name, app_version, app_version_suffix)

    module_naming_scheme = ActiveMNS()

    init_modulepaths = os.path.join("/app/modules/all", *module_naming_scheme.det_init_modulepaths(ec))

    modules = ['%s/%s%s' % (app_name, app_version, app_version_suffix)]

    tmpl = DOCKERFILE_TMPL_UBUNTU1604
    tempdir = tempfile.mkdtemp(prefix='easybuild-docker')
    fd, temp_dockerfile = tempfile.mkstemp(suffix='Dockerfile.%s-%s%s' % (app_name, app_version, app_version_suffix),
                                           dir=tempdir)
    os.write(fd, tmpl.format(easybuild_version=VERSION,
                             os_deps=' '.join(os_deps),
                             easybuild_filename=easybuild_filename,
                             init_modulepaths=init_modulepaths,
                             modules=' '.join(modules)))
    os.close(fd)
    run_cmd(['docker', '--version'], path=tempdir)
    shutil.rmtree(tempdir)


def package_docker(easyconfigs):
    """Build out the tools into a docker image"""
    check_docker_packaging()

    generate_docker_image(easyconfigs)
