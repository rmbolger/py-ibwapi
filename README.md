# ibwapi

A low level, lightweight client for interacting with the Infoblox WAPI.

```python
>>> import ibwapi
>>> wapi = ibwapi.Client('grid.example.com', ('admin','infoblox'), wapi_version='2.13.4')
>>> resp = wapi.get('record:a', {'name:':'myhost.example.com'}, return_fields=['default','comment'])
>>> resp
[{'_ref': 'record:a/ZG5zLmJpbmRfYSQuMS5uZXQuZHZvbHZlLmRzLGRjMSwxMC4xNy4xLjMx:myhost.example.com/Internal', 'comment': 'My Host', 'ipv4addr': '192.168.100.1', 'name': 'myhost.example.com', 'view': 'Internal'}]
>>> wapi.update(resp[0]['_ref'], {'comment':'New Comment'})
'record:a/ZG5zLmJpbmRfYSQuMS5uZXQuZHZvbHZlLmRzLGRjMSwxMC4xNy4xLjMx:myhost.example.com/Internal'
```

## Installing and Supported Versions

ibwapi is available on PyPI:

```console
$ python -m pip install ibwapi
```

ibwapi relies heavily on the [Requests](https://pypi.org/project/requests/) and will generally follow its supported Python versions which is currently 3.8+.
