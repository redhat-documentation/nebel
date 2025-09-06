'''
Created on January 2, 2019

@author fbolton
'''

from __future__ import absolute_import
from __future__ import print_function
import os
import sys
import re

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

        # Misha 2025/06/28 fixing failure to output main file
        if type=="main":
            return("main-new.adoc")

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
        # Misha 2025/06/28 fixing failure to output main file
        if type == 'main':
            return(".")
        elif type == 'assembly':
            return os.path.join(self.context.ASSEMBLIES_DIR, category)
        elif type in ['procedure', 'concept', 'reference', 'module']:
            return os.path.join(self.context.MODULES_DIR, category)
        else:
            print('ERROR: Unknown module Type: ' + str(type))
            sys.exit()

    def module_or_assembly_path(self, metadata):
        return os.path.join(self.module_dirpath(metadata), self.name_of_file(metadata))

    # Misha 2025/05/06: added support fot context creation/ID referencing and for prefixlines for metadata
    def create(self, metadata, filecontents = None, clobber = False, prefixlines = [], context = False, parentcontext = "", assemblypathname = ""):


        type = metadata['Type'].lower()
        filename = self.name_of_file(metadata)
        dirpath = self.module_dirpath(metadata)
        if not os.path.exists(dirpath):
            os.makedirs(dirpath)
        filepath = os.path.join(dirpath, filename)
        #debug output
        print(f"create {filepath}")
        if os.path.exists(filepath) and not clobber:
            print('INFO: File already exists, skipping: ' + filename)
            return filepath
        with open(filepath, 'w') as filehandle:
            # Misha 2025/05/06: added context for assembly
            if context and type=="assembly":
                filehandle.write("ifdef::context[:parent-context: {context}]\n")


            # Misha 2025/05/06: added prefixlines
            if context:
                for l in prefixlines:
                    filehandle.write(l)
            filehandle.write('// Metadata created by nebel\n')
            filehandle.write('//\n')
            for field in self.context.optionalMetadataFields:
                if (field in metadata) and (field.lower() != 'title') and (field.lower() != 'includefiles'):
                    filehandle.write('// ' + field + ': ' + metadata[field] + '\n')
            filehandle.write('\n')


            # Misha 2025/05/06: added context referencing
            module_id=metadata['ModuleID']
            if context:
                module_id+="_{context}"
            # Misha 2025/06/30 no header for main
            if not (('Type' in metadata) and (metadata['Type']=='main')):
                filehandle.write('[id="' + module_id + '"]\n')

            # Misha 2025/05/08: added links.csv
            # Misha 2025/06/30 no link exists for main
            if context and not (('Type' in metadata) and (metadata['Type']=='main')):
                links_csv=open("links.csv","a")
                if 'ConvertedFromID' in metadata:
                    original_id=metadata['ConvertedFromID']
                else:
                    original_id=metadata['ModuleID']
                link_context=parentcontext
                if link_context.strip()=="":
                    link_context="{context}"
                links_csv.write(original_id+","+assemblypathname+"#"+metadata['ModuleID']+"_"+link_context+"\n")
                links_csv.close()

            if filecontents is not None:

                # If filecontents is provided, write the contents verbatim
                # Misha 2025/06/30 no header for main
                if not (('Type' in metadata) and (metadata['Type']=='main')):
                    filehandle.write('= ' + metadata['Title'] + '\n')

                # Misha 2025/05/06: added context for assembly
                # Misha 2025/07/02: handle context for main
                if context and type in ["assembly","main"]:
                    filehandle.write("\n:context: " + metadata['ModuleID'] + "\n")
                    if filecontents[0].strip() != "":
                        filehandle.write("\n")


                filehandle.writelines(filecontents)

                # Misha 2025/05/06: added context for assembly
                if context and type=="assembly":
                    filehandle.write("ifdef::parent-context[:context: {parent-context}]\n")
                    filehandle.write("ifndef::parent-context[:!context:]\n")


                return filepath
            elif type == 'module':
                # Cannot use a template, because we do not know the exact module type
                filehandle.write('= ' + metadata['Title'] + '\n')
                return filepath
            else:
                # Generate contents from template
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
