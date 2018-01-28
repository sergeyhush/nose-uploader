from nose_uploader.plugin import UploadManager


def test_upload_method():
    u = UploadManager('tests')
    assert u.upload_method == u.save_to_json_file
    u = UploadManager('http://upload.test.com')
    assert u.upload_method == u.save_to_http
    u = UploadManager(None)
    assert u.upload_method == u.save_to_json_file
    u = UploadManager('')
    assert u.upload_method == u.save_to_json_file
