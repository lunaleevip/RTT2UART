#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PyInstaller hook for requests module
确保 requests 及其所有依赖都被正确打包
"""

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# 收集 requests 的所有子模块
hiddenimports = collect_submodules('requests')

# 收集 urllib3 的所有子模块
hiddenimports += collect_submodules('urllib3')

# 收集 charset_normalizer
hiddenimports += collect_submodules('charset_normalizer')

# 收集 certifi（SSL 证书）
hiddenimports += collect_submodules('certifi')

# 收集 idna
hiddenimports += collect_submodules('idna')

# 添加 email 模块的所有子模块
hiddenimports += [
    'email',
    'email.mime',
    'email.mime.text',
    'email.mime.multipart',
    'email.mime.base',
    'email.mime.application',
    'email.mime.audio',
    'email.mime.image',
    'email.mime.message',
    'email.mime.nonmultipart',
    'email.parser',
    'email.message',
    'email.utils',
    'email.encoders',
    'email.header',
    'email.charset',
    'email.errors',
    'email.generator',
    'email.policy',
    'email.contentmanager',
    'email.feedparser',
    'email.iterators',
    'email.quoprimime',
    'email._parseaddr',
    'email._policybase',
    'email._encoded_words',
    'email._header_value_parser',
]

# 收集 certifi 的证书文件
datas = collect_data_files('certifi')

