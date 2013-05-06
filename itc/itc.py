# Copyright (c) 2009-2012 Simon Kennedy.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Contributors:
#     Simon Kennedy <code@sffjunkie.co.uk>

__version__ = '0.3.3'
__author__ = 'Simon Kennedy <code@sffjunkie.co.uk>'

ITUNES_9 = 208
ITUNES_OLD = 216

from array import array
import struct
import os.path
import zlib

def enum(**enums):
    return type('Enum', (), enums)

class ITCException(Exception):
    pass

class ITCWarning(Warning):
    pass

class EasyPNG(object):
    def __init__(self, compression=0):
        self.compression = compression
        self.color_type = enum(greyscale=0, truecolor=2, indexed=3,
                               greyscale_alpha=4, truecolor_alpha=6)
    
    def write(self, image, fp):
        self._writes = fp
        self._writes.write('\x89\x50\x4e\x47\x0d\x0a\x1a\x0a')
        self._write_header(image[0], image[1],
                           8, self.color_type.truecolor_alpha)
        self._write_argb_data(image[0], image[1], image[2], image[5])
        self._write_end()
    
    def _write_box(self, name, data, length):
        if length > 0:
            self._writes.write(struct.pack('!L4s%dsl' % length,
                length, name, data,
                zlib.crc32(name+data)))
        else:
            self._writes.write(struct.pack('!L4sl', 0, name, zlib.crc32(name)))
        
    def _write_header(self, width, height, depth, color_type, compression=0,
                      filter_=0, interlace=0):
        data = struct.pack('!IIBBBBB', width, height, depth, color_type,
                           compression, filter_, interlace)
        self._write_box('IHDR', data, 13)

    def _write_data(self, data):
        compress = zlib.compressobj(self.compression)
        compressed = compress.compress(data.tostring())
        compressed += compress.flush()
        length = len(compressed)
        
        self._write_box('IDAT', compressed, length)
    
    def _write_argb_data(self, width, height, argb_data, length):
        data = array('B')
        for y in range(height):
            data.append(0)
            for x in range(width):
                offset = ((y * width) + x) * 4
                data.append(ord(argb_data[offset+1]))
                data.append(ord(argb_data[offset+2]))
                data.append(ord(argb_data[offset+3]))
                data.append(ord(argb_data[offset]))
        
        self._write_data(data)
        
    def _write_end(self):
        self._write_box('IEND', '', 0)
    

class ITCFile(object):
    def __init__(self, mode=ITUNES_9, quiet=False):
        self._HANDLER = {
            'itch': self._parse_itch,
            'artw': self._parse_artw,
            'item': self._parse_item,
        }
        
        self.filename = ''
        self.library = ''
        self.track = ''
        self.images = []
        self.image_data = self._ImageData(self)
        self.image_offset = mode
        self.quiet = quiet

    @staticmethod
    def can_handle(filename):
        fp = open(filename, 'rb')
        fp.seek(4)
        sig = fp.read(4)
        fp.close()
        if sig == 'itch':
            return 'itc'
        else:
            return None
    
    def read(self, filename, list_only=False):
        self.filename = filename
        self.library = ''
        self.track = ''
        del self.images[:]

        self._rs = open(filename, 'rb')
        self._list_only = list_only
        
        done = False
        while not done:
            done = self._read_frame()
            
        self._rs.close()
        
    def add_image(self, filename, width, height):
        _f, ext = os.path.splitext(filename)
        if ext.lower() == '.jpg':
            format_ = 'JPG'
        elif ext.lower() == '.png':
            format_ = 'PNG'
        else:
            raise ITCException(('Unhandled image file extension. Must be '
                                'either .jpg or .png'))
       
        fp = open(filename, 'rb')
        data = fp.read()
        data_size = fp.tell()
        info = (width, height, data, format_, 'local', data_size)
        self.images.append(info)
        fp.close()

    def write(self, filename=''):
        if filename == '':
            if self.filename != '':
                filename = self.filename
            else:
                raise ITCException('You must supply a filename to write()')
        
        self._ws = open(filename, 'wb')
        self._ws.write(struct.pack('!L0004sLLLL0004s', 284, 'itch',
                                   2, 2, 2, 0, 'artw'))
        self._ws.write('\0' * 256)
        
        for x in range(len(self.images)):
            self._write_image(x)
            
        self._ws.close()

    def _write_image(self, num):
        info = self.images[num]
        image_data = info[2]
        
        if image_data is None:
            raise ITCWarning(('Image number %02d has no data and will not be '
                              'written to the file.') % (num+1))
    
        width = info[0]
        height = info[1]
        
        format_ = info[3]
        if format_ == 'PNG':
            iformat = 'PNGf'
        elif format_ == 'JPG':
            iformat = '\x00\x00\x00\x0d'
        elif format_ == 'ARGB':
            iformat = ''
        else:
            raise ITCException(('Invalid format specified (%s) must be either '
                                'JPG or PNG') % format)
            
        method = info[4]
        if method == 'local':
            imethod = 'locl'
        elif method == 'download':
            imethod = 'down'
        else:
            raise ITCException('Invalid method specified (%s)' % method)

        image_len = info[5]
        size = image_len + self.image_offset

        item_header = struct.pack('!L0004sL', size, 'item', self.image_offset)
        item_header += self.info_preamble
        item_header += struct.pack('!QQ004s0004s', self.library, self.track,
            imethod, iformat)
        item_header += '\0' * 4
        item_header += struct.pack('!LL0003sLL', width, height, '\0' * 3,
                                   width, height)

        item_header_len = len(item_header)

        self._ws.write(item_header)
        self._ws.write('\0' * (self.image_offset - item_header_len - 4))
        self._ws.write(struct.pack('0004s', 'data'))
        
        if self.image_offset == ITUNES_OLD:
            self._ws.write('\0\0\0\0')
        
        self._ws.write(image_data)

    class _ImageData(list):
        def __init__(self, itc_file):
            self._itc_file = itc_file
        
        def __getitem__(self, index):
            return self._itc_file.images[index][2]
            
        def __setitem__(self, index, data):
            self._itc_file.images[index][2] = data
            self._itc_file.images[index][5] = len(data)

    def export_image(self, filename, num=1, all_=False):
        if num > len(self.images):
            raise IndexError(('Invalid image number specified (%d). ITC file '
                'only contains %d image(s)') % (num, len(self.images)))

        if num < 1:
            raise IndexError('Image number must be >= 1')

        if all_:
            if not self.quiet:
                print('Extracting all images from %s' % filename)
                
            for x in range(len(self.images)):
                self._export_image_data('%s-%02d' % (filename, x+1), x)
        else:
            if not self.quiet:
                print('Extracting image %02d from %s' % (num, filename))
                
            self._export_image_data('%s-%02d' % (filename, num), num - 1)
                
    def _read_frame(self):
        _pos = self._rs.tell()
        
        data = self._rs.read(8)
        if len(data) == 8:
            size, frame = struct.unpack('!L0004s', data)
    
            self._handle_frame(frame, size)
            
            return False
        else:
            return True

    def _parse_itch(self, frame, size):
        self._rs.seek(16, os.SEEK_CUR)
        subframe = struct.unpack('0004s', self._rs.read(4))[0]
        self._handle_frame(subframe, size)

    def _parse_artw(self, frame, size):
        # Assuming this is a hold-over from a previous ITC format and 
        # is where the artwork was stored at some point in time.
        self._rs.seek(256, os.SEEK_CUR)

    def _parse_item(self, frame, size):
        start = self._rs.tell()
        self.image_offset = struct.unpack('!L', self._rs.read(4))[0]

        # 16 byte preamble for ITUNES_9 & 20 after ITUNES_OLD. 
        # The reason for this unclear.
        # ITUNES_OLD also has extra 4 bytes before image data to account for the
        # 8 bytes difference
        if self.image_offset == ITUNES_9:
            self.info_preamble = self._rs.read(16)
        elif self.image_offset == ITUNES_OLD:
            self.info_preamble = self._rs.read(20)
        
        library, track, imethod, iformat = struct.unpack('!QQ0004s0004s',
                                                         self._rs.read(24))
        
        if self.library == '':
            self.library = library
        elif self.library == library:
            pass
        else:
            raise ITCWarning(('Images with multiple library IDs found. Only '
                              'the first found will be used '
                              '(%s).') % self.library)
        
        if self.track == '':
            self.track = track
        elif self.track == track:
            pass
        else:
            raise ITCWarning(('Images with multiple track IDs found. Only the '
                              'first found will be used (%s).') % self.track)
        
        method = ''
        if imethod == 'locl':
            method = 'local'
        elif imethod == 'down':
            method = 'download'
            
        # TODO: Confirm that downloaded and local images use the same
        # format identifiers
        format_ = ''
        if iformat == 'PNGf' or iformat == '\x00\x00\x00\x0e':
            format_ = 'PNG'
        elif iformat == '\x00\x00\x00\x0d':
            format_ = 'JPEG'
        elif iformat == 'ARGb':
            format_ = 'ARGB'
        
        self._rs.seek(4, os.SEEK_CUR)
        width, height = struct.unpack('!LL', self._rs.read(8))

        image_pos = start + self.image_offset - 8
        self._rs.seek(image_pos)
        
        data_size = size - self.image_offset
        
        if self._list_only:
            data = None
            self._rs.seek(data_size, os.SEEK_CUR)
        else:
            data = self._rs.read(data_size)
        
        self.images.append((width, height, data, format_, method, data_size))

    def _export_image_data(self, filename, num):
        if num < 0:
            pass
        
        img = self.images[num]
                
        if not self.quiet:
            print(('    %02d, width=%d, height=%d, format=%s, location=%s, '
                'length=%d') % (num+1, img[0], img[1], img[3], img[4], img[5]))
        
        extension = ''
        if img[3] == 'PNG' or img[3] == 'ARGB':
            extension = '.png'
        elif img[3] == 'JPEG':
            extension = '.jpg'

        fp = open('%s%s' % (filename, extension), 'wb')
        
        if img[3] != 'ARGB':
            fp.write(img[2])
        else:
            p = EasyPNG()
            p.write(img, fp)
        
        fp.close()

    def _handle_frame(self, frame, size):
        try:
            handler = self._HANDLER[frame]
        except:
            handler = None
            
        if handler is not None:
            handler(frame, size)


if __name__ == "__main__":
    import sys
    import glob
    from optparse import OptionParser
    
    parser = OptionParser(usage='python %s [options] filespec' % sys.argv[0])
    parser.add_option('-l', '--list', dest='list', action='store_true', default=False, help='list image information and exit.')
    parser.add_option('-n', '--number', dest='number', default=-1, help='only output image number NUMBER.', metavar='NUMBER')
    parser.add_option('-b', '--basename', dest='basename', default='', help='base name for output files appended with the image number and extension.')
    parser.add_option('-d', '--directory', dest='directory', default='', help='base directory for output files.')
    parser.add_option('-a', '--add', dest='add', default='', help='add an image. IMGSPEC=filename:width:height', metavar='IMGSPEC')
    parser.add_option('-s', '--set', dest='set', default='', help='set the library and track IDs. LIBSPEC=library:track', metavar='LIBSPEC')
    parser.add_option('-q', '--quiet', dest='quiet', action='store_true', default=False, help='do not display info when extracting.')

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit()
    
    options, args = parser.parse_args()

    if len(args) != 0:
        files = []
        for pattern in args:
            files.extend(glob.glob(pattern))

        for filename in files:
            is_itc = ITCFile.can_handle(filename)
            if is_itc is not None:
                itc = ITCFile(quiet=options.quiet)
                itc.read(filename, list_only=options.list)
                
                if options.list == True:
                    print('ITC File Information for %s' % filename)
                    for x in range(len(itc.images)):
                        img = itc.images[x]
                        print(('    %02d, width=%d, height=%d, format=%s, '
                            'location=%s, length=%d') % (x+1, img[0], img[1],
                            img[3], img[4], img[5]))

                elif options.add != '':
                    if len(files) > 1:
                        print('Cannot add image to multiple files')
                    else:
                        try:
                            img, width, height = options.add.split(':')
                            width = int(width)
                            height = int(height)
                            itc.add_image(img, width, height)
                            itc.write()
                        except ValueError:
                            print('Invalid width or height. Values must be integers')
                        except Exception, exc:
                            print('Unable to add image %s to ITC file %s' % (img, filename))
                            print(exc.args[-1])
                        
                    sys.exit()
                else:
                    if options.basename == '':
                        d, f = os.path.split(filename)
                        n, e = os.path.splitext(f)

                        if options.directory != '':
                            d = options.directory
                    
                        name = os.path.join(d, n)
                    else:
                        name = options.basename
        
                    if options.number == -1:
                        itc.export_image(name, all_=True)
                    else:
                        try:
                            itc.export_image(name, num=int(options.number))
                        except Exception, exc:
                            print('Error: %s' % exc.args[0])
                            
