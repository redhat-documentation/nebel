"""
tests/test_factory.py
~~~~~~~~~~~~~~~~~~~~~

Automated tests for nebel.factory, focused on the new
``:_mod-docs-content-type:`` and ``[role="_abstract"]`` insertions.

Run with:

    cd /home/broldan/git/nebel
    python -m pytest tests/test_factory.py -v

or with the standard library runner:

    python -m unittest discover -s tests
"""

from __future__ import absolute_import
from __future__ import print_function

import os
import sys
import tempfile
import shutil
import unittest

# Make sure the package root is on the path when running the tests directly.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from nebel.context import NebelContext
from nebel.factory import ModuleFactory, _insert_abstract_role, _content_type_for


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_context(tmpdir):
    """Return a minimal NebelContext whose paths live inside *tmpdir*."""
    ctx = NebelContext()
    ctx.ASSEMBLIES_DIR = os.path.join(tmpdir, 'assemblies')
    ctx.MODULES_DIR    = os.path.join(tmpdir, 'modules')
    ctx.IMAGES_DIR     = os.path.join(tmpdir, 'images')
    ctx.templatePath   = os.path.join(os.path.dirname(__file__), '..', 'template')
    ctx.moduleFactory  = ModuleFactory(ctx)
    return ctx


def _base_metadata(type_, category='testcat', module_id='test-topic', title='Test Topic'):
    return {
        'Type':     type_,
        'Category': category,
        'ModuleID': module_id,
        'Title':    title,
    }


def _read(filepath):
    with open(filepath, 'r') as fh:
        return fh.read()


def _lines_of(filepath):
    with open(filepath, 'r') as fh:
        return fh.readlines()


# ---------------------------------------------------------------------------
# Unit tests for module-level helpers
# ---------------------------------------------------------------------------

class TestContentTypeFor(unittest.TestCase):
    """Tests for the _content_type_for() helper."""

    def test_assembly(self):
        self.assertEqual(_content_type_for('assembly'), 'ASSEMBLY')

    def test_concept(self):
        self.assertEqual(_content_type_for('concept'), 'CONCEPT')

    def test_procedure(self):
        self.assertEqual(_content_type_for('procedure'), 'PROCEDURE')

    def test_reference(self):
        self.assertEqual(_content_type_for('reference'), 'REFERENCE')

    def test_continue_returns_none(self):
        self.assertIsNone(_content_type_for('continue'))

    def test_skip_returns_none(self):
        self.assertIsNone(_content_type_for('skip'))

    def test_module_returns_none(self):
        self.assertIsNone(_content_type_for('module'))

    def test_unknown_returns_none_and_warns(self):
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            result = _content_type_for('bogustype')
        self.assertIsNone(result)
        self.assertIn('WARNING', buf.getvalue())
        self.assertIn('bogustype', buf.getvalue())


class TestInsertAbstractRole(unittest.TestCase):
    """Tests for the _insert_abstract_role() helper."""

    def test_inserts_before_first_paragraph(self):
        lines = ['\n', 'First sentence.\n', 'Second sentence.\n']
        result = _insert_abstract_role(lines)
        self.assertIn('[role="_abstract"]\n', result)
        abstract_idx = result.index('[role="_abstract"]\n')
        first_text_idx = result.index('First sentence.\n')
        self.assertEqual(abstract_idx + 1, first_text_idx)

    def test_idempotent_when_already_present(self):
        lines = ['[role="_abstract"]\n', 'First sentence.\n']
        result = _insert_abstract_role(lines)
        self.assertEqual(result, lines)
        self.assertEqual(result.count('[role="_abstract"]\n'), 1)

    def test_skips_leading_blank_lines(self):
        lines = ['\n', '\n', 'Body text.\n']
        result = _insert_abstract_role(lines)
        abstract_idx = result.index('[role="_abstract"]\n')
        body_idx = result.index('Body text.\n')
        self.assertEqual(abstract_idx + 1, body_idx)

    def test_skips_leading_comments(self):
        lines = ['// A comment\n', 'Body text.\n']
        result = _insert_abstract_role(lines)
        abstract_idx = result.index('[role="_abstract"]\n')
        body_idx = result.index('Body text.\n')
        self.assertEqual(abstract_idx + 1, body_idx)

    def test_skips_leading_attribute_entries(self):
        lines = [':myattr: value\n', 'Body text.\n']
        result = _insert_abstract_role(lines)
        abstract_idx = result.index('[role="_abstract"]\n')
        body_idx = result.index('Body text.\n')
        self.assertEqual(abstract_idx + 1, body_idx)

    def test_skips_leading_include_directives(self):
        lines = ['include::some-file.adoc[]\n', 'Body text.\n']
        result = _insert_abstract_role(lines)
        abstract_idx = result.index('[role="_abstract"]\n')
        body_idx = result.index('Body text.\n')
        self.assertEqual(abstract_idx + 1, body_idx)

    def test_inserts_before_block_attribute(self):
        """A block attribute like [NOTE] is the first substantive line."""
        lines = ['\n', '[NOTE]\n', '====\n', 'Note text.\n', '====\n']
        result = _insert_abstract_role(lines)
        abstract_idx = result.index('[role="_abstract"]\n')
        note_idx = result.index('[NOTE]\n')
        self.assertEqual(abstract_idx + 1, note_idx)

    def test_no_body_text_warns(self):
        import io
        from contextlib import redirect_stdout
        lines = ['\n', '// just a comment\n']
        buf = io.StringIO()
        with redirect_stdout(buf):
            result = _insert_abstract_role(lines)
        self.assertEqual(result, lines)
        self.assertIn('WARNING', buf.getvalue())

    def test_does_not_mutate_original_list(self):
        original = ['\n', 'Body text.\n']
        copy_before = list(original)
        _insert_abstract_role(original)
        self.assertEqual(original, copy_before)


# ---------------------------------------------------------------------------
# Integration tests via ModuleFactory.create()
# ---------------------------------------------------------------------------

class TestModuleFactoryCreate(unittest.TestCase):
    """Tests for ModuleFactory.create() with the new insertions."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.ctx = _make_context(self.tmpdir)
        self.factory = self.ctx.moduleFactory

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Content-type attribute for each module type (filecontents path)
    # ------------------------------------------------------------------

    def _create_with_content(self, type_, content_lines):
        meta = _base_metadata(type_)
        return self.factory.create(meta, filecontents=content_lines, clobber=True)

    def test_assembly_content_type_line(self):
        fp = self._create_with_content('assembly', ['\n', 'Intro paragraph.\n'])
        text = _read(fp)
        self.assertIn(':_mod-docs-content-type: ASSEMBLY\n', text)

    def test_concept_content_type_line(self):
        fp = self._create_with_content('concept', ['\n', 'Concept intro.\n'])
        text = _read(fp)
        self.assertIn(':_mod-docs-content-type: CONCEPT\n', text)

    def test_procedure_content_type_line(self):
        fp = self._create_with_content('procedure', ['\n', 'Step-by-step intro.\n'])
        text = _read(fp)
        self.assertIn(':_mod-docs-content-type: PROCEDURE\n', text)

    def test_reference_content_type_line(self):
        fp = self._create_with_content('reference', ['\n', 'Reference intro.\n'])
        text = _read(fp)
        self.assertIn(':_mod-docs-content-type: REFERENCE\n', text)

    # ------------------------------------------------------------------
    # Placement: content-type line is immediately before [id=] line
    # ------------------------------------------------------------------

    def test_content_type_immediately_before_id_line(self):
        fp = self._create_with_content('procedure', ['\n', 'Intro.\n'])
        lines = _lines_of(fp)
        id_idx = next(i for i, l in enumerate(lines) if l.startswith('[id="'))
        # The line directly above [id=] must be the content-type line
        self.assertTrue(
            lines[id_idx - 1].startswith(':_mod-docs-content-type:'),
            msg='Expected :_mod-docs-content-type: immediately before [id=] line, '
                'got: ' + repr(lines[id_idx - 1])
        )

    def test_content_type_after_metadata_comments(self):
        meta = _base_metadata('concept')
        meta['ConversionStatus'] = 'raw'
        fp = self.factory.create(meta, filecontents=['\n', 'Intro.\n'], clobber=True)
        lines = _lines_of(fp)
        # Find last comment line in metadata block
        last_comment_idx = max(
            i for i, l in enumerate(lines) if l.startswith('//')
        )
        # Next non-blank line after comments should be content-type
        after_comments = [l for l in lines[last_comment_idx + 1:] if l.strip() != '']
        self.assertTrue(
            after_comments[0].startswith(':_mod-docs-content-type:'),
            msg='Expected :_mod-docs-content-type: after metadata comments, '
                'got: ' + repr(after_comments[0])
        )

    # ------------------------------------------------------------------
    # Abstract role insertion (filecontents path)
    # ------------------------------------------------------------------

    def test_abstract_role_inserted_for_assembly(self):
        fp = self._create_with_content('assembly', ['\n', 'Assembly intro.\n'])
        text = _read(fp)
        self.assertIn('[role="_abstract"]\n', text)

    def test_abstract_role_before_first_paragraph(self):
        fp = self._create_with_content('concept', ['\n', 'First sentence.\n'])
        lines = _lines_of(fp)
        abstract_idx = next(i for i, l in enumerate(lines) if l.strip() == '[role="_abstract"]')
        # The line after [role="_abstract"] must be the first paragraph
        self.assertEqual(lines[abstract_idx + 1].strip(), 'First sentence.')

    def test_abstract_role_not_duplicated_when_already_present(self):
        content = ['[role="_abstract"]\n', 'First sentence.\n']
        fp = self._create_with_content('concept', content)
        text = _read(fp)
        self.assertEqual(text.count('[role="_abstract"]'), 1)

    # ------------------------------------------------------------------
    # Idempotency: running create() twice with clobber=True
    # ------------------------------------------------------------------

    def test_idempotent_on_second_create(self):
        content = ['\n', 'Intro paragraph.\n']
        meta = _base_metadata('reference')
        self.factory.create(meta, filecontents=content, clobber=True)
        # Re-run with same content (simulates a re-split)
        fp = self.factory.create(meta, filecontents=content, clobber=True)
        text = _read(fp)
        self.assertEqual(text.count(':_mod-docs-content-type:'), 1)
        self.assertEqual(text.count('[role="_abstract"]'), 1)

    def test_idempotent_abstract_already_in_content(self):
        # Simulate content that was already enriched once
        content = ['[role="_abstract"]\n', 'Intro paragraph.\n']
        fp = self._create_with_content('procedure', content)
        text = _read(fp)
        self.assertEqual(text.count('[role="_abstract"]'), 1)

    # ------------------------------------------------------------------
    # Title and ID replacement still work
    # ------------------------------------------------------------------

    def test_title_written_correctly(self):
        fp = self._create_with_content('concept', ['\n', 'Body.\n'])
        text = _read(fp)
        self.assertIn('= Test Topic\n', text)

    def test_moduleid_written_correctly(self):
        fp = self._create_with_content('concept', ['\n', 'Body.\n'])
        text = _read(fp)
        self.assertIn('[id="test-topic"]\n', text)

    def test_metadata_comments_written(self):
        meta = _base_metadata('concept')
        meta['ConversionStatus'] = 'raw'
        meta['ConvertedFromID']  = 'original-id'
        fp = self.factory.create(meta, filecontents=['\n', 'Body.\n'], clobber=True)
        text = _read(fp)
        self.assertIn('// Metadata created by nebel\n', text)
        self.assertIn('// ConversionStatus: raw\n', text)
        self.assertIn('// ConvertedFromID: original-id\n', text)

    # ------------------------------------------------------------------
    # Template path: content-type added but [role="_abstract"] not doubled
    # ------------------------------------------------------------------

    def test_template_path_has_content_type(self):
        meta = _base_metadata('concept')
        fp = self.factory.create(meta, filecontents=None, clobber=True)
        text = _read(fp)
        self.assertIn(':_mod-docs-content-type: CONCEPT\n', text)

    def test_template_path_abstract_not_duplicated(self):
        """Templates already carry [role="_abstract"]; we must not add another."""
        meta = _base_metadata('procedure')
        fp = self.factory.create(meta, filecontents=None, clobber=True)
        text = _read(fp)
        self.assertEqual(text.count('[role="_abstract"]'), 1)

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_no_body_text_skips_abstract(self):
        """A file with only blank lines after the title gets no abstract role."""
        import io
        from contextlib import redirect_stdout
        content = ['\n', '\n']
        buf = io.StringIO()
        with redirect_stdout(buf):
            fp = self._create_with_content('concept', content)
        text = _read(fp)
        self.assertNotIn('[role="_abstract"]', text)
        self.assertIn('WARNING', buf.getvalue())

    def test_leading_include_then_body(self):
        """A leading include directive is skipped; abstract precedes body."""
        content = ['include::some-file.adoc[]\n', '\n', 'Actual body.\n']
        fp = self._create_with_content('assembly', content)
        lines = _lines_of(fp)
        abstract_idx = next(i for i, l in enumerate(lines) if l.strip() == '[role="_abstract"]')
        body_idx = next(i for i, l in enumerate(lines) if 'Actual body.' in l)
        self.assertEqual(abstract_idx + 1, body_idx)

    def test_leading_comment_then_body(self):
        content = ['// Some comment\n', 'Actual body.\n']
        fp = self._create_with_content('reference', content)
        lines = _lines_of(fp)
        abstract_idx = next(i for i, l in enumerate(lines) if l.strip() == '[role="_abstract"]')
        body_idx = next(i for i, l in enumerate(lines) if 'Actual body.' in l)
        self.assertEqual(abstract_idx + 1, body_idx)

    def test_assembly_file_naming(self):
        meta = _base_metadata('assembly')
        fp = self.factory.create(meta, filecontents=['\n', 'Intro.\n'], clobber=True)
        self.assertTrue(os.path.basename(fp).startswith('assembly-'))

    def test_procedure_file_naming(self):
        meta = _base_metadata('procedure')
        fp = self.factory.create(meta, filecontents=['\n', 'Intro.\n'], clobber=True)
        self.assertTrue(os.path.basename(fp).startswith('proc-'))

    def test_concept_file_naming(self):
        meta = _base_metadata('concept')
        fp = self.factory.create(meta, filecontents=['\n', 'Intro.\n'], clobber=True)
        self.assertTrue(os.path.basename(fp).startswith('con-'))

    def test_reference_file_naming(self):
        meta = _base_metadata('reference')
        fp = self.factory.create(meta, filecontents=['\n', 'Intro.\n'], clobber=True)
        self.assertTrue(os.path.basename(fp).startswith('ref-'))

    def test_existing_file_skipped_without_clobber(self):
        meta = _base_metadata('concept')
        content = ['\n', 'First run.\n']
        fp = self.factory.create(meta, filecontents=content, clobber=True)
        # Second call without clobber must not overwrite
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            fp2 = self.factory.create(meta, filecontents=['\n', 'Second run.\n'], clobber=False)
        self.assertIn('INFO', buf.getvalue())
        text = _read(fp2)
        self.assertIn('First run.', text)
        self.assertNotIn('Second run.', text)


# ---------------------------------------------------------------------------
# Full output structure test (assembly matches expected example from task)
# ---------------------------------------------------------------------------

class TestAssemblyOutputStructure(unittest.TestCase):
    """Verify the full structure of a generated assembly matches the
    expected output shown in the task description."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.ctx = _make_context(self.tmpdir)
        self.factory = self.ctx.moduleFactory

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_assembly_structure(self):
        meta = {
            'Type':               'assembly',
            'Category':           'debezium-using',
            'ModuleID':           'configuring-debezium-logging',
            'Title':              'Configuring {prodname} logging',
            'ConversionStatus':   'raw',
            'ConvertedFromTitle': 'Configuring logging',
            'ConvertedFromFile':  'upstream/debezium/debezium-3.6/documentation/modules/ROOT/pages/operations/logging.adoc',
            'ConvertedFromID':    'configuring-logging',
        }
        content = [
            '\n',
            'By default, {prodname} connectors write all `INFO`, `WARN`, and `ERROR` messages to the console.\n',
            'You can change the default logging configuration by using one of the following methods:\n',
        ]
        fp = self.factory.create(meta, filecontents=content, clobber=True)
        lines = _lines_of(fp)

        # Find key line indices
        content_type_idx = next(i for i, l in enumerate(lines) if l.startswith(':_mod-docs-content-type:'))
        id_idx           = next(i for i, l in enumerate(lines) if l.startswith('[id="'))
        title_idx        = next(i for i, l in enumerate(lines) if l.startswith('= '))
        abstract_idx     = next(i for i, l in enumerate(lines) if l.strip() == '[role="_abstract"]')

        # content-type is directly before [id=]
        self.assertEqual(content_type_idx + 1, id_idx)
        # [id=] is before title
        self.assertLess(id_idx, title_idx)
        # abstract role is after title and before first body text
        self.assertGreater(abstract_idx, title_idx)
        # correct content-type value
        self.assertIn('ASSEMBLY', lines[content_type_idx])
        # first body line is directly after [role="_abstract"]
        first_body = lines[abstract_idx + 1]
        self.assertIn('By default', first_body)


if __name__ == '__main__':
    unittest.main()
