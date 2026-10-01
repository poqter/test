"""Exercise dry-run, complete copy, preservation and rollback on disposable repos."""
import hashlib,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from verify_release import verify,safe_path,file_hash
from apply_release import install,restore

class ReleaseTools(unittest.TestCase):
    def test_apply_and_rollback_preserve_git_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'bundle';target=Path(tmp)/'repo';source.mkdir();target.mkdir()
            for p in (source,target):
                (p/'app.py').write_text('new' if p==source else 'old')
                (p/'calculator_app.py').write_text('calc')
            (source/'new.py').write_text('new helper')
            (target/'old.md').write_text('retired')
            (target/'.git').mkdir();(target/'.git/HEAD').write_text('keep git')
            (target/'.streamlit').mkdir();(target/'.streamlit/secrets.toml').write_text('private')
            (target/'local-note.txt').write_text('keep local')
            files={p.name:{'sha256':file_hash(p)} for p in source.iterdir()}
            (source/'release_manifest.json').write_text(json.dumps({'build_id':'test','files':files,'remove_from_previous_release':['old.md']}))
            install(source,target)
            self.assertEqual((target/'app.py').read_text(),'old')
            result=install(source,target,apply=True)
            self.assertEqual(verify(target)['status'],'PASS')
            self.assertFalse((target/'old.md').exists())
            self.assertEqual((target/'.git/HEAD').read_text(),'keep git')
            self.assertEqual((target/'.streamlit/secrets.toml').read_text(),'private')
            backup=Path(result['backup']);restore(backup,apply=True)
            self.assertEqual((target/'app.py').read_text(),'old')
            self.assertEqual((target/'old.md').read_text(),'retired')
            self.assertFalse((target/'new.py').exists())
            self.assertEqual((target/'local-note.txt').read_text(),'keep local')
    def test_path_escape_is_rejected(self):
        for name in ('../outside','/absolute','C:/outside','folder\\..\\bad'):
            with self.subTest(name=name),self.assertRaises(ValueError):safe_path(Path('/tmp/root'),name)
    def test_manifest_detects_missing_and_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'a').write_bytes(b'a')
            (root/'release_manifest.json').write_text(json.dumps({'build_id':'test','files':{'a':{'sha256':'incorrect'},'missing':{'sha256':'none'}}}))
            result=verify(root);self.assertEqual(result['status'],'FAIL')
            self.assertEqual(result['changed'],['a']);self.assertEqual(result['missing'],['missing'])

if __name__=='__main__':unittest.main()
