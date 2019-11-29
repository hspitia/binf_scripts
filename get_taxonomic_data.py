#!/usr/bin/env python3

import argparse
import os
import pprint as pp
import sys
import subprocess
import textwrap
from collections import defaultdict
from shutil import which

# Global variables
ranks = ['superkingdom', 'phylum', 'class', 'order', 'family', 'genus', 'species']
result_dict = {0 : "failed", 1 : "ok"} 

def setup_argument_parser():
    parser = argparse.ArgumentParser(
        description=textwrap.dedent('''Retrieves taxonomic information from the NCBI taxonomy DB.''')
        )
    
    optional = parser._action_groups.pop()
    required = parser.add_argument_group('required arguments')
    
    # Required arguments
    required.add_argument('-i', '--input_file', type=str, required=1, 
        help="text file with a list of accession numbers for which the taxonomic info will be retrieved.")
    
    
    # Options
    optional.add_argument('-p', '--output_prefix', type=str, default='lineage',
        help="Path to the output prefix file.")
    
    parser._action_groups.append(optional)
    
    return parser

def get_lineage_dicts(accn, taxonomy_data):
    name_row = {"result": 0, "accn" : accn}
    id_row   = {"result": 0, "accn" : accn}
    
    for rank in ranks:
        id_row[rank]   = ''
        name_row[rank] = ''

    if taxonomy_data[0] != 'WebEnv value not found in fetch input' and len(taxonomy_data) > 1:
        for line in taxonomy_data:
            fields = line.split("\t")
            rank   = fields[1]
            taxid  = fields[2]
            name   = fields[3]
            name_row[rank]    = name
            id_row[rank]      = taxid
            name_row["result"] = 1
            id_row["result"]   = 1
    
    return(id_row, name_row)
    

def get_taxonomy_data(accn):
    not_found_str = 'WebEnv value not found in search output - WebEnv1'
    
    get_taxid_cmd = """esearch -db nucleotide -query \"{}\" \
        | efetch -format docsum \
        | xtract -pattern DocumentSummary -element TaxId""".format(
            accn)
    
    proc = subprocess.Popen(get_taxid_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    
    out = err = ""
    try:
        out,err = proc.communicate(timeout=30)
    except TimeoutExpired:
        proc.kill()
        out,err = proc.communicate()
    
    taxid = out.decode("utf-8").rstrip().splitlines()
    # print(taxid)
    taxonomy_data = ['WebEnv value not found in fetch input']
    
    if (len(taxid) == 1) and (taxid[0] != '') and (taxid[0] != 'WebEnv value not found in search output - WebEnv1') :
        efecth_cmd = """efetch -db taxonomy -id \"{}\" -format xml \
            | xtract -pattern Taxon \
                -tab '\n' -sep '\t' \
                -def "NONE" \
                -TAXID TaxId \
                -element "&TAXID",Rank,TaxId,ScientificName \
                -division LineageEx \
                -group Taxon \
                -if Rank -equals superkingdom \
                -or Rank -equals kingdom \
                -or Rank -equals phylum \
                -or Rank -equals class \
                -or Rank -equals order \
                -or Rank -equals family \
                -or Rank -equals genus \
                -or Rank -equals species \
                -tab '\n' -sep '\t' \
                -def "NOT_AVAILABLE" \
                -element "&TAXID",Rank,TaxId,ScientificName""".format(taxid)
        
        proc = subprocess.Popen(efecth_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        
        out = err = ""
        try:
            out,err = proc.communicate(timeout=30)
        except TimeoutExpired:
            proc.kill()
            out,err = proc.communicate()
        
        taxonomy_data = out.decode("utf-8").rstrip().splitlines()
        
    # print(taxonomy_data)
    # sys.exit(1)
    lineage_taxid, lineage_names = get_lineage_dicts(accn, taxonomy_data)
    # pp.pprint(lineage_taxid)
    return(lineage_taxid, lineage_names)

def get_lineage_line(col_names, lineage_dict):
    # headers = ['accn'] + ranks
    # extra_ranks = list(set(lineage_dict.keys()) - set(headers))
    out_line = []
    # pp.pprint(extra_ranks)
    # if lineage_dict["result"] == 1:
    for col in col_names:
        out_line.append(lineage_dict[col])
    
    return(out_line)

def process_input_file(input_file, output_prefix):
    lineages_taxid = []
    lineages_name  = []
    col_names      = ['accn'] + ranks
    
    out_ids_filename   = output_prefix + '.taxids.tsv'
    out_names_filename = output_prefix + '.names.tsv'
    
    out_ids_file   = open(out_ids_filename, 'w')
    out_names_file = open(out_names_filename, 'w')
    header = "\t".join(col_names) + '\n'
    
    out_ids_file.write(header)
    out_names_file.write(header)
    
    print("N\tAccn\tResult")
    counter = 0
    with open(input_file, "r") as i_file:
        for line in i_file:
            accn = line.rstrip()
            counter += 1
            print(f"{counter}\t{accn}\t", end = '')
            taxids, names = get_taxonomy_data(accn)
            print(f"{result_dict[taxids['result']]}")
            
            if (taxids['result'] == 1):
                lineages_taxid.append(taxids)
                lineages_name.append(names)
            
                lineage_ids_line   = "\t".join(get_lineage_line(col_names, taxids)) + '\n'
                lineage_names_line = "\t".join(get_lineage_line(col_names, names)) + '\n'
            
                out_ids_file.write(lineage_ids_line)
                out_names_file.write(lineage_names_line)
    
    out_ids_file.close()
    out_names_file.close()
    
def run():
    parser = setup_argument_parser()

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args          = parser.parse_args()
    input_file    = args.input_file
    output_prefix = args.output_prefix
    
    if which('esearch') is None:
        print("ERROR: NCBI Entrez Direct (EDirect) tools are required.")
        sys.exit(1)
    
    process_input_file(input_file, output_prefix)
    

if __name__ == "__main__":
    run()
