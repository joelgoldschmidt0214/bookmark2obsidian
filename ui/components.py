"""
UIコンポーネントモジュール

このモジュールは、Streamlitベースのユーザーインターフェース表示機能を提供します。
ファイル検証、ブックマーク表示、プレビュー機能、保存機能などのUI関連の
すべての関数を含みます。
"""

import streamlit as st
from pathlib import Path
import os
from bs4 import BeautifulSoup
import requests
from typing import List, Dict, Any, Tuple, Optional
import logging
import re
import time

# 作成したモジュールからのインポート
from ..utils.models import Bookmark, Page, PageStatus
from ..utils.error_handler import error_logger
from ..core.file_manager import LocalDirectoryManager
from ..core.scraper import WebScraper
from ..core.generator import MarkdownGenerator