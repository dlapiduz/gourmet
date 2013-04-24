import os
import yaml
import time

from fabric.api import *
from fabric.colors import yellow, green
from cuisine import *
from helpers import run_as, postgresql_role_ensure

env.user = 'root'
env.timeout = 2400

def setup_server():
    try:
        with open('server_info.yml') as f:
            droplet = yaml.load(f.read())
        print(green('Using current server'))
        env.hosts = [ droplet['ip_address'] ]

    except IOError:
        from dop.client import Client, Droplet
        client = Client(os.environ['DO_CLIENT'], os.environ['DO_API_KEY'])
        DROPLET_SIZE = 63 # for 1GB
        DROPLET_IMAGE = 25489 # Ubuntu 12.10 x64 Server
        DROPLET_REGION = 1 # New York
        SSH_KEY = ["12308"] # My key (use yours!)
        droplet = client.create_droplet('Gitlab',
                                        DROPLET_SIZE,
                                        DROPLET_IMAGE,
                                        DROPLET_REGION,
                                        SSH_KEY)
        #droplet = Droplet(161049, 'Gitlab', 66, 25489, -1, 1551469, -1, '', -1)
        while droplet.status != 'active':
            print(yellow('Waiting for server to start...'))
            time.sleep(10)
            droplet = client.show_droplet(droplet.id)

        print(green('Server created!'))
        stream = file('server_info.yml', 'w')
        yaml.dump(droplet.__dict__, stream)
        env.hosts = [ droplet.ip_address ]


def install_packages():
    packages = [ 'build-essential', 'zlib1g-dev', 'libyaml-dev', 'libssl-dev', 
                 'libgdbm-dev', 'libreadline-dev', 'libncurses5-dev', 'libffi-dev', 
                 'curl', 'git-core', 'openssh-server', 'redis-server', 'postfix', 
                 'checkinstall', 'libxml2-dev', 'libxslt-dev', 'libcurl4-openssl-dev', 
                 'libicu-dev', 'python-dev', 'python-setuptools', 'nginx', 'nginx-common',
                 'postgresql-server-dev-9.1','postgresql-client-9.1', 'vim', 'memcached',
                 'postgresql' ]
    for package in packages:
		package_ensure(package)


def install_ruby():
    dir_ensure('/tmp/ruby')
    with cd('/tmp/ruby'):
        run("curl http://ftp.ruby-lang.org/pub/ruby/1.9/ruby-1.9.3-p392.tar.gz | tar xz")
    with cd('/tmp/ruby/ruby-1.9.3-p392'):
        run('./configure')
        run('make')
        sudo('make install')
        sudo('gem install bundler')


def setup_user():
    mode_sudo()
    user_ensure('git') #, shell="/sbin/false"
    user_ensure('diego', shell="/bin/bash")
    key = file_local_read('files/diego.pub')
    ssh_authorize('diego', key)
    file_update(
        "/etc/sudoers",
        lambda _:text_ensure_line(_, "diego ALL=NOPASSWD: ALL")
    )


def install_shell():
    mode_sudo()
    with cd('/home/git'):
        run_as('git', 'git clone https://github.com/gitlabhq/gitlab-shell.git')
    with cd('/home/git/gitlab-shell'):
        run_as('git', 'git checkout v1.3.0')

    file_upload('/home/git/gitlab-shell/config.yml', 'files/gitlab_shell.yml')
    file_attribs('/home/git/gitlab-shell/config.yml', owner='git', group='git')

    with cd('/home/git/gitlab-shell'):
        run_as('git', './bin/install')


def configure_database():
    mode_sudo()
    postgresql_role_ensure('git', 'password', createdb=True)


def install_gitlab():
    mode_sudo()
    with cd('/home/git'):
        run_as('git', 'git clone https://github.com/gitlabhq/gitlabhq.git gitlab')
    with cd('/home/git/gitlab'):
        run_as('git', 'git checkout 5-0-stable')

    dir_ensure('/home/git/gitlab-satellites', owner='git', group='git')
    dir_ensure('/home/git/gitlab/tmp/pids', owner='git', group='git')
    file_upload('/home/git/gitlab/config/gitlab.yml', 'files/gitlab_config.yml')
    file_attribs('/home/git/gitlab/config/gitlab.yml', owner='git', group='git')
    file_upload('/home/git/gitlab/config/database.yml', 'files/database.yml')
    file_attribs('/home/git/gitlab/config/database.yml', owner='git', group='git')
    with cd('/home/git/gitlab'):
        run_as('git', 'cp config/unicorn.rb.example config/unicorn.rb')
        sudo("gem install charlock_holmes --version '0.6.9'")
        run_as('git', 'bundle install --deployment --without development test mysql')
        run_as('git', 'bundle exec rake db:create RAILS_ENV=production')
        output = run_as('git', 'bundle exec rake gitlab:setup RAILS_ENV=production force=yes')
        auth = output.split('\n')[-2:]
        print("Login Information")
        print(green(auth))


def install_init_script():
    mode_sudo()
    file_upload('/etc/init.d/gitlab', 'files/gitlab_init.sh')
    sudo('chmod +x /etc/init.d/gitlab')
    sudo('chown root:root /etc/init.d/gitlab')
    sudo('update-rc.d gitlab defaults 21')

def start_gitlab():
    sudo('service gitlab start')

def setup_nginx():
    mode_sudo()
    sudo('rm /etc/nginx/sites-enabled/default')
    file_upload('/etc/nginx/sites-available/gitlab', 'files/nginx.conf')
    sudo('ln -s /etc/nginx/sites-available/gitlab /etc/nginx/sites-enabled/gitlab')
    sudo('service nginx restart')

def open_url():
    local('open http://' + env.hosts[0])


def stage():
    install_packages()
    install_ruby()
    setup_user()
    install_shell()
    configure_database()
    install_gitlab()
    install_init_script()
    start_gitlab()
    setup_nginx()
    open_url()