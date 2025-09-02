#!/usr/bin/env python
"""
__author__ = "Keenan Matheny"
__license__ = "SPDX-License-Identifier: MIT"
__status__ = "Beta"
__copyright__ = "Copyright (C) 2024 Broadcom Inc."

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in the
Software without restriction, including without limitation the rights to use,
copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the
Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

import sys, os
import argparse
import traceback
from lib.vdt_base import Base
from cfg.vdt_defaults import set_vdt_config
set_vdt_config()
cfgfile = os.path.join(os.path.dirname(__file__), 'cfg', 'vdt.ini')

class GetProduct(Base):


    def __init__(self, name="vdt_formatter", item_type=None, cfgfile=None, username=None, password=None):

        """
        Initialize a new instance of the class.

        Args:
            name (str): The name of the instance. Default is 'vdt_formatter'.
            item_type (str): The type of item. Default is None.
            cfgfile (str): The configuration file. Default is None.
            username (str): The user name. Default is None.
            password (str): The password. Default is None.

        Attributes:
            cats (list): A list of categories extracted from the configuration file.
            subcats (list): A list of subcategories extracted from the configuration file.
            checks (list): A list of checks extracted from the configuration file.
            check_total (int): The total number of checks.
            username (str): The user name passed as an argument.
            password (str): The password passed as an argument.
            cat_map (list): An empty list for mapping categories.
            report_output (str): An empty string to store the report output.
            report_json (list): An empty list to store the report in JSON format.
        """        
        super().__init__(name=name, item_type=item_type, cfgfile=cfgfile)
    
    def default_detected_product(self):
        default_product = self.vdt_items[0]
        for x in self.vdt_items:
            if 'validation_dir' in self.item_config(x).keys():
                if os.path.exists(self.item_config(x).get('validation_dir')):
                    default_product = x
                    break
        return default_product


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    ProductRunner = GetProduct(name='vdt_main', item_type='product', cfgfile=cfgfile)
    help_msg = "\nAvailable Products:\n"
    default_product = ProductRunner.default_detected_product()
    for item in ProductRunner.vdt_items:
        if default_product == item:
            item_name = f"{item} (default) "
        else:
            item_name = item
        help_msg += f"\n\t- {item_name}: {ProductRunner.item_config(item).get('help')}\n"
    help_msg += "\n"
    parser.add_argument('-p', "--product", choices=ProductRunner.vdt_items, default=default_product, help=help_msg)

    args, unknown = parser.parse_known_args()
    if unknown:
        print("Invalid arguments detected.  Please review the help and try again")
        parser.print_help()
        sys.exit()
    try:
        ProductRunner.run(args.product)
    except Exception as e:

        print(f"There was an issue running the product plugin ({args.product}) "
              "Please review the help and select the correct product if available.\n\n"
              f"Backtrace:\n")
        for frame in traceback.format_exception(e, limit=-5):
            print(frame.replace('\n\n',''))
        parser.print_help()
        sys.exit()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Interrupted')
        try:
            sys.exit(130)
        except SystemExit:
            os._exit(130)

