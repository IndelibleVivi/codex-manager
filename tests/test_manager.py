import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request


REPO_ROOT = Path(__file__).resolve().parents[1]
MANAGER_PATH = REPO_ROOT / 'Codex管理器' / '零件箱' / 'Codex配置管理器.py'
SPEC = importlib.util.spec_from_file_location('codex_manager', MANAGER_PATH)
manager = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(manager)


class ManagerContractTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.home = Path(self.tempdir.name)
        self.root = self.home / '.codex'
        (self.root / 'skills' / 'demo-skill').mkdir(parents=True)
        (self.root / 'tmp').mkdir()
        (self.root / 'sessions').mkdir()
        (self.root / 'AGENTS.md').write_text('# Synthetic home\n', encoding='utf-8')
        (self.root / 'skills' / 'demo-skill' / 'SKILL.md').write_text(
            '---\nname: demo-skill\ndescription: test\n---\n', encoding='utf-8'
        )
        (self.root / 'tmp' / 'leftover.md').write_text('temporary\n', encoding='utf-8')
        (self.root / 'sessions' / 'history.jsonl').write_text('{}\n', encoding='utf-8')
        manager.configure_runtime(
            root=self.root,
            read_only=True,
            open_browser=False,
            quarantine=self.home / 'quarantine',
        )
        self.server = manager.http.server.ThreadingHTTPServer(('127.0.0.1', 0), manager.H)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f'http://{host}:{port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tempdir.cleanup()

    def request_json(self, path, payload=None):
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        request = urllib.request.Request(self.base_url + path, data=data, headers=headers)
        try:
            response = urllib.request.urlopen(request, timeout=2)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, json.loads(response.read().decode('utf-8'))

    def test_meta_reports_selected_root_and_read_only_mode(self):
        status, body = self.request_json('/api/meta')
        self.assertEqual(status, 200)
        self.assertEqual(Path(body['root']), self.root.resolve())
        self.assertTrue(body['readOnly'])

    def test_read_only_file_metadata_disables_mutations(self):
        status, body = self.request_json('/api/file?path=AGENTS.md')
        self.assertEqual(status, 200)
        self.assertFalse(body['editable'])
        self.assertFalse(body['deletable'])
        self.assertTrue(body['readonly'])

    def test_read_only_mode_rejects_every_mutating_endpoint(self):
        cases = [
            ('/api/save', {'path': 'AGENTS.md', 'content': 'changed'}),
            ('/api/delete', {'path': 'AGENTS.md'}),
            ('/api/restore', {'file': 'fixture'}),
            ('/api/purge_item', {'file': 'fixture'}),
            ('/api/empty_quarantine', {}),
            ('/api/clean_group', {'cat': 'junk'}),
            ('/api/new_skill', {'name': 'new-skill'}),
        ]
        for path, payload in cases:
            with self.subTest(path=path):
                status, body = self.request_json(path, payload)
                self.assertEqual(status, 403)
                self.assertFalse(body['ok'])
                self.assertIn('只读模式', body['error'])

        self.assertEqual((self.root / 'AGENTS.md').read_text(encoding='utf-8'), '# Synthetic home\n')
        self.assertFalse((self.root / 'skills' / 'new-skill').exists())
        self.assertFalse((self.home / 'quarantine').exists())

    def test_inventory_uses_the_selected_root_without_mutating_it(self):
        before = sorted(path.relative_to(self.root) for path in self.root.rglob('*'))
        output = self.home / 'inventory.html'
        report = manager.generate_inventory(self.root, output)
        after = sorted(path.relative_to(self.root) for path in self.root.rglob('*'))

        self.assertEqual(before, after)
        self.assertEqual(report['totalFiles'], 4)
        self.assertEqual(report['catTotals']['junk']['Files'], 1)
        self.assertEqual(report['catTotals']['history']['Files'], 1)
        self.assertTrue(output.is_file())
        html = output.read_text(encoding='utf-8-sig')
        self.assertIn('Codex 库存仪表盘', html)
        self.assertIn('demo-skill', html)

    def test_inventory_refuses_to_write_inside_the_selected_root(self):
        output = self.root / 'inventory.html'
        with self.assertRaisesRegex(ValueError, '不能写进被扫描的 Codex 目录'):
            manager.generate_inventory(self.root, output)
        self.assertFalse(output.exists())

    def test_inventory_encodes_filesystem_names_before_embedding_them(self):
        hostile_name = '<img src=x onerror=alert(1)>.md'
        (self.root / hostile_name).write_text('fixture\n', encoding='utf-8')
        output = self.home / 'inventory.html'
        manager.generate_inventory(self.root, output)
        html = output.read_text(encoding='utf-8-sig')
        self.assertNotIn(hostile_name, html)
        self.assertIn('\\u003cimg src=x onerror=alert(1)>.md', html)

    def test_read_only_quarantine_is_neither_exposed_nor_purged(self):
        quarantine = self.home / 'quarantine'
        quarantine.mkdir()
        expired = quarantine / '20000101-000000__old.md'
        expired.write_text('keep in read-only mode\n', encoding='utf-8')
        old_time = time.time() - 10 * 24 * 60 * 60
        expired.touch()
        import os
        os.utime(expired, (old_time, old_time))

        status, body = self.request_json('/api/quarantine')
        self.assertEqual(status, 200)
        self.assertEqual(body, {'items': [], 'disabled': True})
        self.assertTrue(expired.is_file())

    def test_read_write_mode_preserves_the_existing_save_and_delete_flow(self):
        manager.configure_runtime(
            root=self.root,
            read_only=False,
            open_browser=False,
            quarantine=self.home / 'quarantine',
        )
        status, body = self.request_json('/api/file?path=AGENTS.md')
        self.assertEqual(status, 200)
        self.assertTrue(body['editable'])
        self.assertTrue(body['deletable'])

        status, body = self.request_json('/api/save', {'path': 'AGENTS.md', 'content': '# Updated\n'})
        self.assertEqual(status, 200)
        self.assertTrue(body['ok'])
        self.assertEqual((self.root / 'AGENTS.md').read_text(encoding='utf-8'), '# Updated\n')

        status, body = self.request_json('/api/delete', {'path': 'tmp/leftover.md'})
        self.assertEqual(status, 200)
        self.assertTrue(body['ok'])
        self.assertFalse((self.root / 'tmp' / 'leftover.md').exists())
        self.assertEqual(len(list((self.home / 'quarantine').iterdir())), 1)

    def test_macos_launchers_default_to_management_and_scan_only_inventory(self):
        manager_launcher = (
            REPO_ROOT / 'Codex管理器' / '打开 Codex 管理器-macOS.command'
        ).read_text(encoding='utf-8-sig')
        inventory_launcher = (
            REPO_ROOT / 'Codex管理器' / '打开 Codex 库存仪表盘-macOS.command'
        ).read_text(encoding='utf-8-sig')

        self.assertIn('Codex配置管理器.py', manager_launcher)
        self.assertNotIn('--read-only', manager_launcher)
        self.assertIn('--inventory', inventory_launcher)


if __name__ == '__main__':
    unittest.main()
