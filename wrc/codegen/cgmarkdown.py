import re
from wrc.sema.ast import Ruleset, Rule, LabelDecl
from wrc.codegen.cg import CGDocument

H2 = '## {title}\n'
H3 = '### {title}\n'
TITLE = '# <wca-title>{title}\n'
VERSION = '<version>{version}\n'

def special_links_replace(text, urls):
    '''
    Replace simplified Regulations and Guidelines links into actual links.
    'urls' dictionary is expected to provide actual links to the targeted
    Regulations and Guidelines, as well as to the PDF file.
    '''
    match_number = r'([A-Za-z0-9]+)' + r'(\+*)'
    reference_list = [(r'regulations:article:' + match_number, urls['regulations']),
                      (r'regulations:regulation:' + match_number, urls['regulations']),
                      (r'guidelines:article:' + match_number, urls['guidelines']),
                      (r'guidelines:guideline:' + match_number, urls['guidelines']),
                     ]
    anchor_list = [(r'regulations:contents', urls['regulations'] + r'#contents'),
                   (r'guidelines:contents', urls['guidelines'] + r'#contents'),
                   (r'regulations:top', urls['regulations'] + r'#'),
                   (r'guidelines:top', urls['guidelines'] + r'#'),
                   (r'link:pdf', urls['pdf'] + '.pdf'),
                  ]
    retval = text
    for match, repl in reference_list:
        retval = re.sub(match, repl + r'#\1\2', retval)
    for match, repl in anchor_list:
        retval = re.sub(match, repl, retval)
    return retval

def list2html(text):
    '''
    Very simple replacement for lists, no nesting, not even two lists in the
    same 'text'... (yet sufficient for the current regulations)
    Assumes list is in a paragraph.
    '''
    match = r'- (.+)\n'
    replace = r'<li>\1</li>\n'
    text = re.sub(match, replace, text)
    # Set start of list
    text = text.replace('<li>', '</p><ul><li>', 1)
    # Set end of list
    tmp = text.rsplit('</li>', 1)
    return '</li></ul><p>'.join(tmp)

def link2html(text):
    ''' Turns md links to html '''
    match = r'\[([^\]]+)\]\(([^)]+)\)'
    replace = r'<a href="\2">\1</a>'
    return re.sub(match, replace, text)

def simple_md2html(text, urls):
    ''' Convert a text from md to html '''
    retval = special_links_replace(text, urls)
    # Create a par break for double newlines
    retval = re.sub(r'\n\n', r'</p><p>', retval)
    # Create a visual br for every new line
    retval = re.sub(r'\n', r'<br />\n', retval)
    # Do we really need this ? Help reduce the diff to only '\n' diff.
    retval = re.sub(r'"', r'&quot;', retval)
    retval = list2html(retval)
    return link2html(retval)


class WCADocumentMarkDown(CGDocument):
    name = "MarkDown"

    def __init__(self, versionhash, language, pdf):
        super(WCADocumentMarkDown, self).__init__(str)
        self.regset = set()
        self.urls = {'regulations': './', 'guidelines': './', 'pdf': pdf}
        self.language = language
        self.harticle = "\n\n## <article-{num}><{name1}><{name2}> {name}{sep}{title}\n"
        self.guideline = "- {i}) [{label}] {text}"
        self.regulation = "- {i}) {text}"
        self.postreg = '\n'

    # def generate_ul(self, a_list):
    #     """Determines if we should generate th 'ul' around the list 'a_list'"""
    #     return len(a_list) > 0 and (isinstance(a_list[0], Rule) or
    #                                 isinstance(a_list[0], LabelDecl))

    def visitWCADocument(self, document):
        self.codegen += TITLE.format(title=document.title)
        self.codegen += VERSION.format(version=document.version)

        retval = [self.visit(s) for s in document.sections]

        # FIXME do we really need ascii html entities instead of plain utf8 ?
        # self.codegen = self.codegen.encode('ascii', 'xmlcharrefreplace').decode('utf-8')
        return retval.count(False) == 0

    def visitlist(self, o):
        # TODO Indent.
        retval = super(WCADocumentMarkDown, self).visitlist(o)
        return retval

    def visitstr(self, u):
        # if len(u) > 0:
        #     self.codegen += "<p>" + self.md2html(u) + "</p>\n"
        return True

    def visitTableOfContent(self, toc):
        self.codegen += "NOTES HERE, CHECK APPROPRIATE FORMAT (REMOVE THIS LINE)"
        self.codegen += "<table-of-contents>"
        return True

    def visitSection(self, section):
        return super(WCADocumentMarkDown, self).visitSection(section)

    def visitArticle(self, article):
        # "\n\n## <article-{num}><{name1}><{name2}> {name}{sep}{title}\n"
        self.codegen += self.harticle.format(anchor=article.number,
                                             old=article.oldtag,
                                             new=article.newtag,
                                             name=article.name,
                                             title=article.title,
                                             sep=article.sep)
        retval = super(WCADocumentHtml, self).visit(article.intro)
        retval = retval and super(WCADocumentHtml, self).visit(article.content)
        return retval

    def visitSubsection(self, subsection):
        if self.shouldEmitSubsection(self.language, subsection.title):
            self.codegen += H3.format(anchor=anchorizer(subsection.title),
                                      title=subsection.title)
            return super(WCADocumentHtml, self).visitSubsection(subsection)
        return True

    def visitRegulation(self, reg):
        self.codegen += self.regulation.format(i=reg.number,
                                               text=self.md2html(reg.text))
        retval = super(WCADocumentHtml, self).visitRegulation(reg)
        self.codegen += self.postreg
        return retval


    def visitLabelDecl(self, decl):
        self.codegen += self.label.format(name=decl.name, text=decl.text)
        return True

    def visitGuideline(self, guide):
        reg = guide.regname
        linked = reg in self.regset
        label_class = "linked" if linked else ""
        link_attr = 'href="%s#%s"' % (self.urls['regulations'], reg)
        anchor_attr = 'id="#%s"' % guide.number
        attr = link_attr if linked else anchor_attr

        self.codegen += self.guideline.format(i=guide.number,
                                              text=self.md2html(guide.text),
                                              label=guide.labelname,
                                              linked=label_class,
                                              attr=attr)
        return super(WCADocumentHtml, self).visitGuideline(guide)

    def emit(self, ast_reg, ast_guide):
        self.regset = Ruleset().get(ast_reg)
        return super(WCADocumentHtml, self).emit(ast_reg, ast_guide)
