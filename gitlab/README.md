gourmet/gitlab
===============

Fabric/cuisine script to install [gitlab](https://github.com/gitlabhq/gitlabhq) from scratch in [digital ocean](https://www.digitalocean.com/).

## Requirements

- Digital Ocean API keys.
- Fabric and Cuisine python packages

## How to run

1. Set two environment variables `DO_CLIENT`, `DO_API_KEY` with your client id and API key respectively.
2. Run `fab setup_server stage`.