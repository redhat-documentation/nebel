'''
Created on January 2, 2019

@author fbolton
'''

from __future__ import absolute_import
from __future__ import print_function
import os
import sys
import re

# Maps the Nebel ``Type`` annotation (lowercase) to the DITA/modular-docs
# content-type value written as ``:_mod-docs-content-type: <VALUE>``.
# ``continue``, ``skip``, and ``module`` are never written as standalone files
# so they are intentionally absent from this map.
CONTENT_TYPE_MAP = {
    'assembly':  'ASSEMBLY',
    'concept':   'CONCEPT',
    'procedure': 'PROCEDURE',
    'reference': 'REFERENCE',
}

# Regular expressions used for idempotency checks and abstract insertion.
_RE_CONTENT_TYPE_LINE = re.compile(r'^:_mod-docs-content-type:\s+\S')
_RE_ABSTRACT_ROLE     = re.compile(r'^\[role="_abstract"\]')
# Lines that are NOT body text (blank, comment, AsciiDoc attribute entry,
# include directive, or block/role/id attribute line starting with '[').
_RE_NON_BODY = re.compile(
    r'^\s*$'                  # blank line
    r'|^//'                   # comment
    r'^:[\w\-]+:'             # attribute entry  (e.g. `:foo: bar`)
    r'|^include::'            # include directive
    r'|^\[',                  # block attribute / role / id line
    re.VERBOSE
)


def _content_type_for(module_type):
    """Return the ``:_mod-docs-content-type:`` value for *module_type*.

    *module_type* is the lowercased value of the Nebel ``Type`` annotation.
    Returns ``None`` for types that should not receive a content-type line
    (``module``, ``continue``, ``skip``).  Prints a warning and returns
    ``None`` for completely unknown values.
    """
    if module_type in CONTENT_TYPE_MAP:
        return CONTENT_TYPE_MAP[module_type]
    if module_type in ('module', 'continue', 'skip'):
        # These are valid internal types but are never written as standalone
        # modular files, so they require no content-type attribute.
        return None
    print('WARNING: Unknown module Type "' + module_type + '" — '
          ':_mod-docs-content-type: line will not be inserted.')
    return None


def _insert_abstract_role(lines):
    """Return a copy of *lines* with ``[role="_abstract"]`` inserted before
    the first body-text paragraph, following these rules:

    1. Skip leading blank lines, comment lines, AsciiDoc attribute entries
       (``:`foo`:``) and ``include::`` directives — these are not body text.
    2. If the first body-text line is already ``[role="_abstract"]``, leave the
       list unchanged (idempotent).
    3. If *lines* contains no body text at all, emit a warning and return
       *lines* unchanged.

    Lines starting with ``[`` (block attribute / role / id lines) are
    themselves considered non-body so that the abstract is placed *before*
    them only when the very first content encountered is such a block
    attribute.  The heuristic is: skip blanks/comments/attributes/includes,
    then insert before whatever comes next unless it is already
    ``[role="_abstract"]``.
    """
    insert_pos = None
    for i, line in enumerate(lines):
        stripped = line.rstrip('\n')
        # Skip blank lines
        if stripped.strip() == '':
            continue
        # Skip comment lines
        if stripped.lstrip().startswith('//'):
            continue
        # Skip AsciiDoc attribute entries  :name: value
        if re.match(r'^:[\w\-]+:', stripped):
            continue
        # Skip include directives
        if stripped.lstrip().startswith('include::'):
            continue
        # We've found the first substantive line.
        if _RE_ABSTRACT_ROLE.match(stripped):
            # Already present — nothing to do.
            return lines
        insert_pos = i
        break

    if insert_pos is None:
        print('WARNING: No body text found after title — '
              '[role="_abstract"] will not be inserted.')
        return lines

    result = list(lines)
    result.insert(insert_pos, '[role="_abstract"]\n')
    return result


class ModuleFactory:
    def __init__(self, context):
        self.context = context

    def lreplace(self, pat, sub, target):
        if target.startswith(pat):
            return sub + target[len(pat):]
        else:
            return target

    def name_of_file(self, metadata):
        type = metadata['Type'].lower()
        moduleid = metadata['ModuleID']
        if not moduleid.endswith('{context}'):
            coremoduleid = moduleid
        else:
            tmpstr = moduleid.replace('{context}', '')
            regexp = re.compile(r'[_\-]+$')
            result = regexp.search(tmpstr)
            if result is None:
                print('ERROR: Cannot parse ModuleID: ' + moduleid)
                sys.exit()
            coremoduleid = regexp.sub('', tmpstr)
        coremoduleid = coremoduleid.replace('_', '-')
        if type == 'assembly' and not coremoduleid.startswith(self.context.ASSEMBLY_PREFIX):
            return self.context.ASSEMBLY_PREFIX + coremoduleid + '.adoc'
        elif type == 'procedure' and not coremoduleid.startswith(self.context.PROCEDURE_PREFIX):
            return self.context.PROCEDURE_PREFIX + coremoduleid + '.adoc'
        elif type == 'concept' and not coremoduleid.startswith(self.context.CONCEPT_PREFIX):
            return self.context.CONCEPT_PREFIX + coremoduleid + '.adoc'
        elif type == 'reference' and not coremoduleid.startswith(self.context.REFERENCE_PREFIX):
            return self.context.REFERENCE_PREFIX + coremoduleid + '.adoc'
        else:
            # For a generic module of unknown type, do not attach a prefix
            return coremoduleid + '.adoc'

    def normalize_filename(self, filename):
        normalized = filename.replace('_', '-')
        return normalized


    def module_dirpath(self, metadata):
        category = metadata['Category']
        type = metadata['Type'].lower()
        if type == 'assembly':
            return os.path.join(self.context.ASSEMBLIES_DIR, category)
        elif type in ['procedure', 'concept', 'reference', 'module']:
            return os.path.join(self.context.MODULES_DIR, category)
        else:
            print('ERROR: Unknown module Type: ' + str(type))
            sys.exit()

    def module_or_assembly_path(self, metadata):
        return os.path.join(self.module_dirpath(metadata), self.name_of_file(metadata))

    def create(self, metadata, filecontents=None, clobber=False):
        """Create a modular AsciiDoc file from *metadata* and optional *filecontents*.

        For every generated file this method now inserts:

        * ``:_mod-docs-content-type: <VALUE>`` immediately **before** the
          ``[id="..."]`` line (after the metadata comment block).  The value
          is derived from the ``Type`` annotation:
          ``ASSEMBLY``, ``CONCEPT``, ``PROCEDURE``, or ``REFERENCE``.

        * ``[role="_abstract"]`` on its own line immediately before the first
          body-text paragraph.  Leading blank lines, comments, AsciiDoc
          attribute entries, and ``include::`` directives are skipped when
          locating the first body paragraph.  If the content already starts
          with ``[role="_abstract"]``, no duplicate is inserted (idempotent).

        When *filecontents* is ``None`` the file is generated from a template.
        Templates already contain ``[role="_abstract"]`` in the correct place,
        so abstract-role insertion is skipped for the template path.
        """
        type = metadata['Type'].lower()
        filename = self.name_of_file(metadata)
        dirpath = self.module_dirpath(metadata)
        if not os.path.exists(dirpath):
            os.makedirs(dirpath)
        filepath = os.path.join(dirpath, filename)
        if os.path.exists(filepath) and not clobber:
            print('INFO: File already exists, skipping: ' + filename)
            return filepath

        content_type_value = _content_type_for(type)

        with open(filepath, 'w') as filehandle:
            # --- Metadata comment block ---
            filehandle.write('// Metadata created by nebel\n')
            filehandle.write('//\n')
            for field in self.context.optionalMetadataFields:
                if (field in metadata) and (field.lower() != 'title') and (field.lower() != 'includefiles'):
                    filehandle.write('// ' + field + ': ' + metadata[field] + '\n')
            filehandle.write('\n')

            # --- Content-type attribute (before [id=] line) ---
            if content_type_value is not None:
                filehandle.write(':_mod-docs-content-type: ' + content_type_value + '\n')

            # --- ID and title ---
            filehandle.write('[id="' + metadata['ModuleID'] + '"]\n')
            if filecontents is not None:
                # filecontents path: write title then body with abstract role
                filehandle.write('= ' + metadata['Title'] + '\n')
                enriched = _insert_abstract_role(filecontents)
                filehandle.writelines(enriched)
                return filepath
            elif type == 'module':
                # Cannot use a template because we do not know the exact module type
                filehandle.write('= ' + metadata['Title'] + '\n')
                return filepath
            else:
                # Generate contents from template.
                # Templates already contain [role="_abstract"], so we do NOT
                # call _insert_abstract_role() here.
                templatefile = os.path.join(self.context.templatePath, type + '.adoc')
                with open(templatefile, 'r') as templatehandle:
                    if 'Title' in metadata:
                        # Replace the title from the first line of the template
                        templatehandle.readline()
                        filehandle.write('= ' + metadata['Title'] + '\n')
                    # Process the rest of the file
                    for line in templatehandle:
                        if line.startswith('//INCLUDE') and ('IncludeFiles' in metadata):
                            for includedfilepath in metadata['IncludeFiles'].split(','):
                                filehandle.write('include::' + os.path.relpath(includedfilepath, dirpath) + '[leveloffset=+1]\n\n')
                        else:
                            filehandle.write(line)
        return filepath
