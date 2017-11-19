# About

This is a little script which converts a LyX file (which may include images) into an HTML file and "publishes" it on a [local copy](#start-blogging) of your Jekyll-based blog. The script can be [integrated](#integration) in LyX.

# Usage

`LyXBlog [--update] <input file> <blog base dir> <assets relative dir>`

where:

* `--update` is used when you want to update an article and it's OK to overwrite existing files
* `input file` is the LyX file to publish
* `blog base dir` is the base dir of the local copy of your blog
* `assets relative dir` is the relative dir (e.g. "`assets`") of the directory where to put the images

# Requirements

`lyx.exe` and `pandoc.exe` must be in your *search path* and the script requires **Python 3**.

# Front matter

Every LyX file needs to contain a *front matter* which is a wrapper around the *real* Jekyll front matter. The part between the two "`---`" is copied *verbatim* into the HTML file.

**IMPORTANT:** You need to insert the front matter as *commented TeX code* (CTRL-L) right at the beginning of the file.

Here's the format:

```
%LyXBlog-start
%html_file_name: ML_notes
%---
%layout:         post
%title:          Title of the post
%date:           YYYY-MM-DD
%summary:        This is shown on the page which lists the articles.
%                Except for the first two lines and the last line, which are specific to LyXBlog,
%                everything else is copied verbatim (after removing all the '%').
%---
%LyXBlog-end
```

The `html_file_name` value is used by LyXBlog to name the HTML file. Use the basename of the file without any extension just like in the example above.

# What the script does

The script does the following:

1. it converts article.lyx to article.tex with `lyx.exe`
2. it converts article.tex to article.html with `pandoc.exe` (--mathjax)
3. it extracts the front matter from article.tex
3. it adds the front matter to article.html and copy the file into *_post* with its proper name: <br>
   `<%date>-<%html_file_name>.html`
4. it handles the images in article.lyx by copying them to the directory <br>
   `<blog base dir>\<assets relative dir>\<%date>-<%html_file_name>` <br>
   and fixing the references to the images.

# <a name="integration"></a>Calling the script from LyX

Go to `Tools->Preferences...` and create the following two (fake) file formats:

![first file format](file_format1.png)

![second file format](file_format2.png)

Remember to click on *New* and *Apply*.

Then create the following two converters, one with and the other without `--update`:

![first converter](converter1.png)

![second converter](converter2.png)

The field `Converter` deserves an explanation:
- I'm calling `python.exe` with the full path because LyX modifies its private *search path* to make it point to its copy of Python 2.
- If you are on Windows, you need to use "`/`" for the Python path and "`\`" for the other paths. This is a "portability issue", AFAICT.
- `$$r$$i` is the full path of the LyX document.

Remember to click on *Add*, *Apply* and *Save*.

After you've done all that, you can run the script from `File->Export`.

# <a name="start-blogging"></a>An easy way to start blogging on GitHub Pages

1. install [ruby](https://www.ruby-lang.org/en/)
2. install [bundler](http://bundler.io/) by executing <br>
   `gem install bundler`
3. fork a [theme](http://jekyllthemes.org/)
4. rename your fork to `<Your GitHub Username>.github.io`
5. clone the fork:<br>
   `git clone https://github.com/<Your GitHub Username>/<Your GitHub Username>.github.io`
6. go inside the local dir of the just-cloned repository
7. execute `bundle install`

Now you can see your local blog by executing `bundle exec jekyll serve` and by going to `http://127.0.0.1:4000`.
