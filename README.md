# ibwapi

A low level, lightweight client for interacting with the Infoblox WAPI.

```python
>>> import ibwapi
>>> wapi = ibwapi.Client(
...     'grid.example.com',     # grid master FQDN
...     ('admin','infoblox'),   # auth tuple
...     wapi_version='2.13.4'   # WAPI version (optional)
... )
>>> resp = wapi.get(
...     'record:a',                         # object type
...     {'name:':'myhost.example.com'},     # filters
...     return_fields=['default','comment'] # return fields
... )
>>> resp
[{'_ref': 'record:a/ZG5zLmJpbmRfYSQuMS5uZXQuZHZvbHZlLmRzLGRjMSwxMC4xNy4xLjMx:myhost.example.com/Internal', 'comment': 'My Host', 'ipv4addr': '192.168.100.1', 'name': 'myhost.example.com', 'view': 'Internal'}]
>>> wapi.update(
...     resp[0]['_ref'],            # object ref
...     {'comment':'New Comment'}   # updated fields
... )
'record:a/ZG5zLmJpbmRfYSQuMS5uZXQuZHZvbHZlLmRzLGRjMSwxMC4xNy4xLjMx:myhost.example.com/Internal'
```

## Installing and Supported Versions

ibwapi is available on PyPI:

```console
$ python -m pip install ibwapi
```

ibwapi relies heavily on the [Requests](https://pypi.org/project/requests/) and will generally follow its supported Python versions which is currently 3.8+.
