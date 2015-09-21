# !/usr/bin/env python
# -*- coding: utf-8  -*-
# Created by mqingyn on 2015/2/10.
import json
import weakref
import itertools


class BormError(Exception):
    def __init__(self, reason):
        self.reason = reason
        super(BormError, self).__init__(reason)


class FieldError(BormError):
    """ field error"""


class RequiredError(BormError):
    """require error"""


class ValidateError(BormError):
    def __init__(self, reason, field=None):
        self.field = field
        super(ValidateError, self).__init__(reason)


class Field(object):
    def __init__(self, **kw):
        self.__datatype = kw.get('datatype', None)
        self.__default = kw.get('default', None)
        self.__required = kw.get('required', False)
        self.__info = kw.get('info', '')
        self.__showname = kw.get('name', None)
        self.__quiet_check = kw.get('quiet_check', False)
        self._name = None
        self._model = None

    @property
    def name(self):
        return self.__showname or self._name

    @property
    def default(self):
        d = self.__default
        return d() if callable(d) else d

    @property
    def value(self):
        if self._model:
            return self._model[self._name]

    @property
    def info(self):
        return self.__info

    @property
    def datatype(self):
        return self.__datatype

    @property
    def required(self):
        return self.__required

    @property
    def quiet_check(self):
        return self.__quiet_check

    def __str__(self):
        return '<%s:%s>' % (self.__class__.__name__, str(self.datatype),)

    def check(self, value):
        raise NotImplementedError

    def clean(self):
        self._model[self._name] = self.default


class BuildinTypeField(Field):
    def __init__(self, convert_args=None, **kw):
        self.__convert_args = convert_args

        super(BuildinTypeField, self).__init__(**kw)

    @property
    def convert_args(self):
        return self.__convert_args

    def check(self, value):

        if value is not None:
            if not isinstance(value, self.datatype):
                try:
                    if isinstance(value, basestring) and not value:
                        value = self.default

                    if self.convert_args:
                        return self.datatype(value, **self.convert_args)
                    return self.datatype(value)
                except:
                    raise FieldError('invalid check field "%s" %s,need %s.' % (self.name, type(value), str(self.datatype),))

            else:
                return value

        else:
            return self.default


class OriginCheckMixin(object):
    checked_err = None

    def __init__(self, **kw):

        self.__origin_value = None
        self.__quiet_check = kw.pop('quiet_check', False)
        super(OriginCheckMixin, self).__init__(**kw)

    @property
    def origin_value(self):
        return self.__origin_value

    def check(self, value):

        try:
            return super(OriginCheckMixin, self).check(value)
        except Exception as e:
            if self.__quiet_check:
                self.__origin_value = value
                self.checked_err = e
                return self.default
            else:
                raise


class BOField(OriginCheckMixin, Field):
    def __init__(self, **kw):
        datatype = kw.pop("datatype", '')
        if not issubclass(datatype, BOModel):
            raise FieldError('invalid check %s,need %s.' % (str(datatype), str(BOModel),))

        super(BOField, self).__init__(datatype=datatype, **kw)

    def check(self, value):
        if value is not None:
            if not isinstance(value, self.datatype):
                raise FieldError('invalid check %s,need %s.' % (type(value), str(self.datatype),))
            else:
                return value
        else:
            return self.default


class StringField(OriginCheckMixin, BuildinTypeField):
    def __init__(self, encoding='utf8', blank=False, **kw):
        self.__encoding = encoding
        self._init(encoding, blank, **kw)

    def _init(self, encoding, blank=False, **kw):
        default = kw.pop("default", '' if blank else None)
        super(StringField, self).__init__(default=default, datatype=str, **kw)

    @property
    def encoding(self):
        return self.__encoding

    def check(self, value):
        if value is not None:
            return self.safestr(self.safeunicode(value), encoding=self.encoding)
        else:
            return self.default

    def safestr(self, obj, encoding='utf-8'):

        if isinstance(obj, unicode):
            return obj.encode(encoding)
        elif isinstance(obj, str):
            return obj
        elif hasattr(obj, 'next'):  # iterator
            return itertools.imap(self.safestr, obj)
        else:
            return str(obj)

    def safeunicode(self, obj, encoding='utf-8'):

        t = type(obj)
        if t is unicode:
            return obj
        elif t is str:
            return obj.decode(encoding)
        elif t in [int, float, bool]:
            return unicode(obj)
        elif hasattr(obj, '__unicode__') or isinstance(obj, unicode):
            return unicode(obj)
        else:
            return str(obj).decode(encoding)


class UnicodeField(StringField):
    def _init(self, encoding, blank=False, **kw):
        default = kw.pop("default", u'' if blank else None)
        super(StringField, self).__init__(default=default, datatype=unicode, **kw)

    def check(self, value):
        if value is not None:
            return self.safeunicode(value, encoding=self.encoding)
        else:
            return self.default


class _BOList(list):
    def todict(self, ignore_null=False, ignore_default=False):
        return [l if not hasattr(l, 'todict') else l.todict(ignore_null=ignore_null, ignore_default=ignore_default) for
                l in self]


class _BODict(dict):
    def todict(self, ignore_null=False, ignore_default=False):
        return {k: v if not hasattr(v, 'todict') else v.todict(ignore_null=ignore_null, ignore_default=ignore_default) \
                for k, v in self.iteritems()}


class ListField(OriginCheckMixin, BuildinTypeField):
    def __init__(self, generictype=None, ruleout=True, **kw):
        default = kw.pop("default", [])
        self.__generictype = generictype
        self.__ruleout = ruleout
        super(ListField, self).__init__(default=default, datatype=_BOList, **kw)

    def check(self, value):
        value = super(ListField, self).check(value)
        if value:
            if self.__generictype and self.__ruleout:
                return _BOList([v for v in value if isinstance(v, self.__generictype)])
            else:
                return value


class DictField(OriginCheckMixin, BuildinTypeField):
    def __init__(self, generictype=None, ruleout=True, **kw):
        default = kw.pop("default", {})
        self.__generictype = generictype
        self.__ruleout = ruleout
        super(DictField, self).__init__(default=default, datatype=_BODict, **kw)

    def check(self, value):
        value = super(DictField, self).check(value)
        if value:
            if self.__generictype and self.__ruleout:

                return _BODict({k: v for k, v in value.iteritems() if isinstance(v, self.__generictype)})
            else:
                return value


def _check_num(minv, maxv, val, dtype):
    if maxv < minv:
        raise FieldError('max value must be bigger than min value.')
    if minv is not None:
        val = max(val, dtype(minv))
    if maxv is not None:
        val = min(val, dtype(maxv))

    return val


class FloatField(OriginCheckMixin, BuildinTypeField):
    def __init__(self, **kw):
        default = kw.pop("default", 0.0)
        self.minv = kw.pop("min", None)
        self.maxv = kw.pop("max", None)

        super(FloatField, self).__init__(default=default, datatype=float, **kw)

    def check(self, value):
        val = super(FloatField, self).check(value)
        return _check_num(self.minv, self.maxv, val, float)


class IntegerField(OriginCheckMixin, BuildinTypeField):
    def __init__(self, **kw):
        default = kw.pop("default", 0)
        self.minv = kw.pop("min", None)
        self.maxv = kw.pop("max", None)
        super(IntegerField, self).__init__(default=default, datatype=int, **kw)

    def check(self, value):
        val = super(IntegerField, self).check(value)
        return _check_num(self.minv, self.maxv, val, int)


class BoolField(OriginCheckMixin, BuildinTypeField):
    def __init__(self, **kw):
        default = kw.pop("default", False)
        super(BoolField, self).__init__(default=default, datatype=bool, **kw)

    def check(self, value):
        if isinstance(value, basestring):
            val = value.lower()
            if val in ('false', 'null', 'none', '0',):
                value = False

        return super(BoolField, self).check(value)


class BOMetaclass(type):
    def __new__(mcs, name, bases, attrs):
        if name == 'BOModel':
            return type.__new__(mcs, name, bases, attrs)

        mappings = {}
        validator = []

        for base in bases:
            base_mappings = getattr(base, '__mappings__', {})
            mappings.update(base_mappings)

            base_validate = getattr(base, '__validator__', None)
            if base_validate:
                if isinstance(base_validate, list):
                    validator += base_validate
                else:
                    validator.append(base_validate)

        for k, v in attrs.iteritems():
            if isinstance(v, Field):
                mappings[k] = v

        [attrs.pop(k) for k in mappings.iterkeys() if k in attrs]

        attrs['__mappings__'] = mappings
        if attrs.get('__validator__', None):
            validator.append(attrs['__validator__'])
        else:
            attrs['__validator__'] = None
        attrs['__validator__'] = validator

        return type.__new__(mcs, name, bases, attrs)


class BOModel(dict):
    __metaclass__ = BOMetaclass

    def __init__(self, quiet_check=False, **kwargs):
        kw = {}
        self.quiet_check = quiet_check
        for k, v in self.__mappings__.iteritems():

            if isinstance(v, Field):
                v._model = weakref.proxy(self)
                v._name = k
                if k in kwargs:
                    try:
                        kw[k] = v.check(kwargs.pop(k))
                    except:
                        if quiet_check or v.quiet_check:
                            kw[k] = v.check(v.default)
                        else:
                            raise

                else:
                    kw[k] = v.check(v.default)


        super(BOModel, self).__init__(**kw)

    def clean_all(self):
        for k, v in self.__mappings__.iteritems():
            self[k] = v.check(v.default)

    def validate(self, quiet=False):
        errors = []

        def vald_(key, val):
            validator_method = None
            for valid in self.__validator__[::-1]:
                validator_method = getattr(valid, 'validate_%s' % key, None)
                if validator_method:
                    break
            try:
                validator_method and validator_method(self, self[key], val)
            except ValidateError as e:
                e.field = key
                if not quiet:
                    raise e
                else:
                    errors.append(e)

        for k, v in self.__mappings__.iteritems():
            if v.required and self[k] is None and v.default is None:
                require_error = RequiredError('"%s" is a required field.' % k)
                if quiet:
                    errors.append(require_error)
                else:
                    raise RequiredError('"%s" is a required field.' % k)
            if self.__validator__:
                vald_(k, v)

        return errors

    def __getattr__(self, key):
        try:
            if key.endswith('__field') and key.rstrip('__field') in self.__mappings__:
                return self.__mappings__.get(key.rstrip('__field'), None)

            return self[key]

        except KeyError:
            raise AttributeError(r"'BaseBO' object has no attribute '%s'" % key)

    def __set(self, key, value):
        if key in self.__mappings__:
            field = self.__mappings__[key]
            try:
                value = field.check(value)
            except:
                if self.quiet_check or field.quiet_check:
                    value = field.check(field.default)
                else:
                    raise

        self[key] = value

    def __setattr__(self, key, value):
        self.__set(key, value)

    def __repr__(self):
        return '<%s ' % self.__class__.__name__ + dict.__repr__(self) + '>'

    def update(self, kwargs):
        if not kwargs: kwargs = {}
        for k, v in kwargs.iteritems():
            self.__set(k, v)

    def todict(self, exclude=None, include=None, ignore_null=False, ignore_default=False):
        if not exclude:
            exclude = []
        if not include:
            include = self.__mappings__.keys()

        def v_tolist_(k, field):
            v = getattr(self, k)
            if field.required and v is None and field.default is None:
                raise RequiredError('"%s" is a required field.' % k)

            if v:
                return v.todict(ignore_null=ignore_null, ignore_default=ignore_default) if hasattr(v, 'todict') else v
            else:
                return v

        def ignoreit_(k, field):
            val = getattr(self, k)
            if ignore_null:
                if val is None:
                    return True
            if ignore_default:
                if val == field.default:
                    return True

            return False

        if exclude:
            func = lambda k: k not in exclude
        else:
            func = lambda k: k in include

        return {v.name: v_tolist_(k, v) for k, v in self.__mappings__.iteritems()
                if func(k) and not ignoreit_(k, v)}

    def dumps(self, dicts=None, exclude=None, include=None, **kwargs):
        dict = dicts or self.todict(exclude=exclude, include=include)
        return json.dumps(dict, **kwargs)

    @classmethod
    def parse_list(cls, lists, exclude=None, include=None, ignore_null=False, ignore_default=False):
        if not lists: lists = []

        def _(l):
            if hasattr(l, 'todict'):
                return l.todict(exclude=exclude, include=include, ignore_null=ignore_null,
                                ignore_default=ignore_default)
            else:
                return l

        return [_(l) for l in lists]

    @classmethod
    def parse_dict(cls, dicts, ignore_null=False, ignore_default=False):
        if not dicts: dicts = {}

        def _(l):
            if hasattr(l, 'todict'):
                return l.todict(ignore_null=ignore_null,
                                ignore_default=ignore_default)
            else:
                return l

        return {k: _(obj) for k, obj in dicts.iteritems()}
